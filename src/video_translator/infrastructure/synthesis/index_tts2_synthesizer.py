"""Implementacion de SpeechSynthesizer usando IndexTTS-2.5 (Bilibili/IndexTeam).

Este es el motor de sintesis de voz recomendado por defecto para doblaje: es un
modelo zero-shot con clonacion de voz a partir de una muestra corta, soporte
multilingue nativo que incluye espanol, y sobre todo **control explicito de la
duracion del habla generada** — la primera arquitectura autoregresiva que
resuelve esto de forma nativa, pensada expresamente para sincronizacion
audiovisual en doblaje de video (a diferencia de XTTS v2, que genera a ritmo
libre y depende de estirar/comprimir el audio despues con ffmpeg, degradando
timbre y prosodia cuando el ajuste es grande).

Instalacion (no esta en PyPI, se instala desde el repo oficial):
    ./scripts/setup_index_tts2.sh
lo que clona https://github.com/index-tts/index-tts en third_party/index-tts,
lo instala en modo editable, y descarga los checkpoints de
IndexTeam/IndexTTS-2.5 desde Hugging Face.

Referencia: https://github.com/index-tts/index-tts

RENDIMIENTO — una sola pasada de inferencia por segmento:
Una version anterior generaba primero "a ritmo natural", media la duracion
resultante, y si se alejaba demasiado del objetivo, volvia a generar una
SEGUNDA vez con un duration_factor corregido — hasta el doble de inferencias
del modelo (el paso mas caro de todo el pipeline) por cada segmento. Ahora se
estima el duration_factor de antemano con una heuristica de caracteres por
segundo (sin necesidad de generar nada primero), se genera UNA sola vez, y el
ajuste fino final (si el resultado no encaja exacto) lo hace ffmpeg
(``fit_to_duration``, barato, sin techo de compresion) en vez del modelo. En
un video con miles de segmentos esto es la diferencia entre horas y minutos.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from video_translator.application.synthesis_job import SynthesisJob
from video_translator.domain.exceptions import SynthesisError
from video_translator.infrastructure.synthesis.audio_mixing import (
    concatenate_segments,
    fit_to_duration,
)
from video_translator.utils.logging_config import get_logger
from video_translator.utils.warning_collector import note_stat

if TYPE_CHECKING:
    from indextts.infer_v2_5 import IndexTTS2
    from torch import Tensor

logger = get_logger(__name__)

# IndexTTS-2.5 espera codigos de idioma en mayusculas (EN, ES, ZH, JA, AR).
_LANG_CODE_MAP = {"es": "ES", "en": "EN", "zh": "ZH", "ja": "JA", "ar": "AR"}

# Heuristica de ritmo de habla en espanol (caracteres por segundo), usada
# SOLO para estimar un duration_factor razonable de entrada sin tener que
# generar audio primero para medirlo. No necesita ser exacta: el ajuste fino
# final lo hace ffmpeg de todas formas.
_CHARS_PER_SECOND_ES = 15.0

# Rango de duration_factor que el modelo soporta de forma nativa.
_MIN_DURATION_FACTOR = 0.5
_MAX_DURATION_FACTOR = 2.0


def _split_batched_codes(codes: Tensor, stop_mel_token: int) -> list[Tensor]:
    """Recorta cada fila de un batch de codigos generados (B, seq_len) en su
    propio stop_mel_token y devuelve UNA lista de tensores (uno por item,
    cada uno shape (1, code_len_i)) -- nunca compartiendo la fila entre
    items. Extraida a funcion pura (sin dependencias de IndexTTS2) para
    poder testear esta logica sin el modelo real.

    Regresion cubierta: una version anterior devolvia siempre la fila 0 del
    batch para todos los items (solo variando el largo del recorte), asi que
    el batch entero terminaba sonando con el contenido del primer item. Y
    quedarse con `codes[i][:1]` cuando code_len==0 (generacion degenerada,
    el primer token YA es stop) intentaba decodificar el propio
    stop_mel_token como codigo real, que excede el vocabulario del codec
    semantico (IndexError). Aqui, en cambio, un code_len==0 produce
    correctamente un tensor vacio (1, 0), igual que hace infer_generator
    para el caso analogo de un solo item.
    """
    result = []
    for i, code in enumerate(codes):
        if stop_mel_token not in code:
            code_len = len(code)
        else:
            idx = (code == stop_mel_token).nonzero(as_tuple=False)
            code_len = idx[0].item() if idx.numel() > 0 else len(code)
        result.append(codes[i : i + 1, :code_len])
    return result


class IndexTTS2Synthesizer:
    def __init__(
        self,
        model_dir: str = "third_party/index-tts/checkpoints",
        cfg_path: str = "third_party/index-tts/checkpoints/config.yaml",
        use_bf16: bool = True,
        default_speaker_wav: Path | None = None,
        ffmpeg_binary: str = "ffmpeg",
        device: str | None = None,
        use_torch_compile: bool = False,
        num_beams: int = 3,
        gpt_batch_size: int = 4,
    ) -> None:
        self._model_dir = model_dir
        self._cfg_path = cfg_path
        self._use_bf16 = use_bf16
        self._default_speaker_wav = default_speaker_wav
        self._ffmpeg = ffmpeg_binary
        # None = dejar que IndexTTS2 autodetecte (cuda > mps > cpu). Se puede
        # forzar explicitamente (p.ej. "cpu") — importante en macOS cuando se
        # corren varios workers en paralelo, ver container.py: varios
        # procesos tomando Metal (MPS) a la vez es una combinacion inestable
        # que puede crashear el driver de GPU y reiniciar el sistema.
        self._device = device
        # Compila el sub-modelo s2mel (difusion, no autoregresivo) con
        # torch.compile -- mismos pesos, mismo calculo, sin perdida de
        # calidad. Ya viene cableado dentro de IndexTTS2 (enable_torch_compile
        # en su constructor) pero apagado por defecto ahi tambien. Paga un
        # costo de compilacion la primera inferencia de cada proceso worker;
        # solo conviene si el proceso sintetiza suficientes segmentos para
        # amortizarlo.
        self._use_torch_compile = use_torch_compile
        # El GPT autoregresivo usa num_beams=3 por defecto internamente (no
        # expuesto en el README). Probado en CPU: bajarlo a 1 no acelero
        # gpt_gen_time (HuggingFace generate() procesa los beams como
        # dimension de batch en un solo forward pass, casi gratis con margen
        # de CPU libre) -- no hay razon para bajarlo, arriesgaria calidad sin
        # ganar velocidad. Configurable solo por si acaso en otro hardware.
        self._num_beams = num_beams
        # Cuantos textos como maximo se procesan en una sola pasada del GPT
        # autoregresivo (ver synthesize_batch). Mas grande satura mejor la
        # CPU, pero si los textos del grupo tienen longitudes muy distintas,
        # el mas largo determina cuanto tardan TODOS los del batch (los
        # cortos "esperan" con padding) — un tope moderado evita ese peor
        # caso. 1 = deshabilita el batching (cada "grupo" es un solo item).
        self._gpt_batch_size = max(1, gpt_batch_size)
        self._tts: IndexTTS2 | None = None  # carga perezosa: el modelo pesa varios GB

    def _load(self) -> IndexTTS2:
        if self._tts is None:
            try:
                from indextts.infer_v2_5 import IndexTTS2  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover
                raise SynthesisError(
                    "IndexTTS-2.5 no esta instalado. Ejecuta: ./scripts/setup_index_tts2.sh "
                    "(clona el repo oficial y descarga los checkpoints)."
                ) from exc
            logger.info(
                "index_tts2.loading_model",
                model_dir=self._model_dir,
                device=self._device or "auto",
                use_torch_compile=self._use_torch_compile,
            )
            kwargs = {"device": self._device} if self._device else {}
            self._tts = IndexTTS2(
                cfg_path=self._cfg_path,
                model_dir=self._model_dir,
                use_bf16=self._use_bf16,
                use_torch_compile=self._use_torch_compile,
                **kwargs,
            )
        return self._tts

    def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        target_duration_seconds: float,
        speaker_reference_wav: Path | None = None,
        language: str = "es",
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        speaker_wav = speaker_reference_wav or self._default_speaker_wav
        if speaker_wav is None:
            raise SynthesisError(
                "IndexTTS-2.5 requiere una muestra de voz de referencia para clonar el "
                "timbre (zero-shot). Pasa --speaker-wav con un .wav de 6-15s del hablante "
                "original."
            )

        tts = self._load()
        lang_code = _LANG_CODE_MAP.get(language.lower(), language.upper())
        duration_factor = self._estimate_duration_factor(text, target_duration_seconds)

        try:
            kwargs = {"duration_factor": duration_factor} if duration_factor is not None else {}
            tts.infer(
                spk_audio_prompt=str(speaker_wav),
                text=text,
                lang=lang_code,
                output_path=str(output_path),
                verbose=False,
                num_beams=self._num_beams,
                **kwargs,
            )
        except TypeError:
            # Version del modelo instalada sin soporte de duration_factor:
            # reintenta sin el (sigue siendo UNA sola pasada de inferencia).
            logger.debug("index_tts2.duration_factor_unsupported")
            try:
                tts.infer(
                    spk_audio_prompt=str(speaker_wav),
                    text=text,
                    lang=lang_code,
                    output_path=str(output_path),
                    verbose=False,
                    num_beams=self._num_beams,
                )
            except Exception as exc:
                raise SynthesisError(f"Fallo sintetizando segmento con IndexTTS-2.5: {exc}") from exc
        except Exception as exc:
            raise SynthesisError(f"Fallo sintetizando segmento con IndexTTS-2.5: {exc}") from exc

        # Ajuste final de precision: ffmpeg (barato, sin techo de compresion),
        # no una segunda pasada del modelo. Ver docstring del modulo.
        fit_to_duration(output_path, target_duration_seconds, ffmpeg_binary=self._ffmpeg)
        return output_path

    @staticmethod
    def _estimate_duration_factor(text: str, target_seconds: float) -> float | None:
        """Estima un duration_factor de entrada sin generar audio primero,
        a partir de la longitud del texto. No necesita ser precisa: solo le
        da al modelo un punto de partida razonable para que ffmpeg tenga
        menos que corregir despues (mejor calidad que partir siempre de 1.0)."""
        if target_seconds <= 0:
            return None
        estimated_natural_seconds = len(text) / _CHARS_PER_SECOND_ES
        if estimated_natural_seconds <= 0:
            return None
        factor = estimated_natural_seconds / target_seconds
        return max(_MIN_DURATION_FACTOR, min(_MAX_DURATION_FACTOR, factor))

    def concatenate_segments(
        self, segment_audio_paths: list[tuple[float, Path, float]], total_duration: float, output_path: Path
    ) -> Path:
        return concatenate_segments(
            segment_audio_paths, total_duration, output_path, ffmpeg_binary=self._ffmpeg
        )

    def synthesize_batch(self, jobs: list[SynthesisJob]) -> None:
        """Batching real del paso mas caro de la sintesis (``gpt_gen_time``):
        agrupa los jobs por voz de referencia y arma UNA sola pasada del GPT
        autoregresivo para varios textos a la vez, en vez de una llamada
        completa de ``infer()`` por cada uno.

        Diseño deliberadamente conservador: el resto del pipeline (decodificar
        codigos semanticos, s2mel, bigvgan) sigue procesando cada item POR
        SEPARADO con el mismo calculo que ``synthesize_segment`` — solo se
        recorta del batch ya generado, sin batchear esa parte. Esto evita
        tener que lidiar con padding/mascaras en la difusion (s2mel) y el
        vocoder, donde un error seria mucho mas dificil de detectar (podria
        sonar bien pero llevar contenido mezclado de otra muestra).

        Esto reimplementa una porcion del metodo interno
        ``IndexTTS2.infer_generator`` (third_party/index-tts/indextts/infer_v2_5.py)
        porque esa clase no expone una forma publica de batchear varios
        textos — si el paquete vendorizado se actualiza, revisar que esta
        logica siga siendo fiel a la version nueva (ver comentarios con
        numeros de linea aproximados de la version usada al escribir esto).
        """
        if not jobs:
            return
        tts = self._load()

        by_speaker: dict[Path, list[SynthesisJob]] = {}
        for job in jobs:
            speaker_wav = job.speaker_reference_wav or self._default_speaker_wav
            if speaker_wav is None:
                raise SynthesisError(
                    "IndexTTS-2.5 requiere una muestra de voz de referencia para clonar el "
                    "timbre (zero-shot). Pasa --speaker-wav con un .wav de 6-15s del hablante "
                    "original."
                )
            by_speaker.setdefault(speaker_wav, []).append(job)

        for speaker_wav, speaker_jobs in by_speaker.items():
            # Ordenar por longitud de texto: agrupa los de tamaño parecido en
            # el mismo batch, minimizando el padding desperdiciado entre el
            # mas corto y el mas largo de cada lote.
            ordered = sorted(speaker_jobs, key=lambda j: len(j.text))
            for i in range(0, len(ordered), self._gpt_batch_size):
                self._synthesize_batch_same_speaker(tts, speaker_wav, ordered[i : i + self._gpt_batch_size])

    def _synthesize_batch_same_speaker(
        self, tts: IndexTTS2, speaker_wav: Path, jobs: list[SynthesisJob]
    ) -> None:
        import torch
        import torch.nn.functional as F
        import torchaudio
        from indextts.utils.tokenizer import lang_to_token

        spk_audio_prompt = str(speaker_wav)

        # Filtra los jobs cuyo texto no entra en un solo segmento del GPT
        # (mismo presupuesto que usa split_text_by_tokens internamente): se
        # sintetizan por el camino secuencial de siempre, sin batchear, en
        # vez de arriesgar una implementacion propia de multi-segmento.
        capacity = tts.gpt.text_pos_embedding.emb.num_embeddings
        lang_prefix_len = len(tts.tokenizer.encode("<|es|> ", allowed_special="all"))
        budget = max(1, min(120, capacity - 2) - lang_prefix_len)
        batchable: list[SynthesisJob] = []
        for job in jobs:
            lang_prefix = f"<|{job.language.lower()}|> "
            token_len = len(tts.tokenizer.encode(lang_prefix + job.text, allowed_special="all"))
            if token_len <= budget:
                batchable.append(job)
            else:
                logger.debug("index_tts2.batch_fallback_text_too_long", text_len=len(job.text))
                self.synthesize_segment(
                    text=job.text,
                    output_path=job.output_path,
                    target_duration_seconds=job.target_duration_seconds,
                    speaker_reference_wav=speaker_wav,
                    language=job.language,
                )
        if not batchable:
            return

        t0 = time.monotonic()

        # ---- Setup por hablante: identico a infer_generator (ver lineas
        # ~611-696 de infer_v2_5.py), reusando el mecanismo de cache propio
        # de IndexTTS2 (cache_spk_cond/cache_emo_cond) para no duplicar
        # trabajo si el mismo proceso worker ya sintetizo con esta voz antes.
        verbose = False
        if tts.cache_spk_cond is None or tts.cache_spk_audio_prompt != spk_audio_prompt:
            audio, sr = tts._load_and_cut_audio(spk_audio_prompt, 15, verbose)
            audio_22k = torchaudio.transforms.Resample(sr, 22050)(audio)
            audio_16k = torchaudio.transforms.Resample(sr, 16000)(audio)
            inputs = tts.extract_features(audio_16k, sampling_rate=16000, return_tensors="pt")
            input_features = inputs["input_features"].to(tts.device)
            attention_mask = inputs["attention_mask"].to(tts.device)
            spk_cond_emb = tts.get_emb(input_features, attention_mask)
            ref_mel = tts.mel_fn(audio_22k.to(spk_cond_emb.device).float())
            ref_target_lengths = torch.LongTensor([ref_mel.size(2)]).to(ref_mel.device)
            audio_16k_2 = torchaudio.transforms.Resample(sr, 16000)(
                tts._load_and_cut_audio(spk_audio_prompt, 15, verbose)[0]
            )
            feat = torchaudio.compliance.kaldi.fbank(
                audio_16k_2.to(ref_mel.device), num_mel_bins=80, dither=0, sample_frequency=16000
            )
            feat = feat - feat.mean(dim=0, keepdim=True)
            style = tts.campplus_model(feat.unsqueeze(0))
            prompt_condition = tts.s2mel.models["length_regulator"](
                spk_cond_emb, ylens=ref_target_lengths, n_quantizers=3, f0=None
            )[0]
            tts.cache_spk_cond = spk_cond_emb
            tts.cache_s2mel_style = style
            tts.cache_s2mel_prompt = prompt_condition
            tts.cache_spk_audio_prompt = spk_audio_prompt
            tts.cache_mel = ref_mel
        style = tts.cache_s2mel_style
        prompt_condition = tts.cache_s2mel_prompt
        spk_cond_emb = tts.cache_spk_cond
        ref_mel = tts.cache_mel

        # emo_audio_prompt = spk_audio_prompt siempre en nuestro uso (no
        # exponemos una voz de referencia emocional separada).
        if tts.cache_emo_cond is None or tts.cache_emo_audio_prompt != spk_audio_prompt:
            emo_audio, _ = tts._load_and_cut_audio(spk_audio_prompt, 15, verbose, sr=16000)
            emo_inputs = tts.extract_features(emo_audio, sampling_rate=16000, return_tensors="pt")
            emo_input_features = emo_inputs["input_features"].to(tts.device)
            emo_attention_mask = emo_inputs["attention_mask"].to(tts.device)
            emo_cond_emb = tts.get_emb(emo_input_features, emo_attention_mask)
            tts.cache_emo_cond = emo_cond_emb
            tts.cache_emo_audio_prompt = spk_audio_prompt
        emo_cond_emb = tts.cache_emo_cond

        # ---- Tokenizar y armar el batch (B, L), padding a derecha con el
        # stop_text_token: prepare_gpt_inputs (model_v2.py) descarta
        # cualquier start/stop token de la secuencia y vuelve a alinear con
        # padding IZQUIERDO por su cuenta, asi que el valor/lado de este
        # padding de entrada no afecta el resultado, solo debe ser
        # reconocible como "no es texto real".
        segment_tokens = []
        for job in batchable:
            lang_prefix = f"<|{job.language.lower()}|> "
            toks = tts.tokenizer.encode(lang_prefix + job.text, allowed_special="all")
            toks = torch.IntTensor(toks).unsqueeze(0).to(tts.device)
            segment_tokens.append(F.pad(toks, (0, 1), value=tts.gpt.stop_text_token))
        max_len = max(t.shape[1] for t in segment_tokens)
        padded = [
            F.pad(t, (0, max_len - t.shape[1]), value=tts.gpt.stop_text_token) for t in segment_tokens
        ]
        text_tokens = torch.cat(padded, dim=0)
        langs = torch.LongTensor([lang_to_token(job.language) for job in batchable]).to(tts.device)

        do_sample = True
        top_p, top_k, temperature = 0.8, 30, 0.8
        length_penalty, repetition_penalty, max_mel_tokens = 0.0, 10.0, 1500

        with torch.no_grad():
            with torch.amp.autocast(text_tokens.device.type, enabled=tts.dtype is not None, dtype=tts.dtype):
                emovec = tts.gpt.merge_emovec(
                    spk_cond_emb,
                    emo_cond_emb,
                    torch.tensor([spk_cond_emb.shape[-1]], device=text_tokens.device),
                    torch.tensor([emo_cond_emb.shape[-1]], device=text_tokens.device),
                    alpha=1.0,
                )
                codes, _ = tts.gpt.inference_speech(
                    spk_cond_emb,
                    text_tokens,
                    langs,
                    emo_cond_emb,
                    cond_lengths=torch.tensor([spk_cond_emb.shape[-1]], device=text_tokens.device),
                    emo_cond_lengths=torch.tensor([emo_cond_emb.shape[-1]], device=text_tokens.device),
                    emo_vec=emovec,
                    campplus_embedding=style,
                    wav=spk_audio_prompt,
                    do_sample=do_sample,
                    top_p=top_p,
                    top_k=top_k,
                    temperature=temperature,
                    num_return_sequences=1,
                    length_penalty=length_penalty,
                    num_beams=self._num_beams,
                    repetition_penalty=repetition_penalty,
                    max_generate_length=max_mel_tokens,
                )

            per_item_codes = _split_batched_codes(codes, tts.stop_mel_token)

            # ---- Downstream (semantic_codec -> s2mel -> bigvgan): CADA item
            # por separado, con el mismo calculo exacto que synthesize_segment
            # (nada de esto esta batcheado), tomando su propia porcion ya
            # recortada del batch generado arriba.
            for job, code in zip(batchable, per_item_codes):
                duration_factor = (
                    self._estimate_duration_factor(job.text, job.target_duration_seconds) or 1.0
                )
                with torch.amp.autocast(text_tokens.device.type, enabled=False):
                    S_infer = tts.semantic_codec.decode(code)
                    target_lengths = torch.LongTensor(
                        [int(S_infer.shape[1] * 1.72 * duration_factor)]
                    ).to(code.device)
                    cond = tts.s2mel.models["length_regulator"](
                        S_infer, ylens=target_lengths, n_quantizers=3, f0=None
                    )[0]
                    cat_condition = torch.cat([prompt_condition, cond], dim=1)
                    vc_target = tts.s2mel.models["cfm"].inference(
                        cat_condition,
                        torch.LongTensor([cat_condition.size(1)]).to(cond.device),
                        ref_mel,
                        style,
                        None,
                        25,
                        inference_cfg_rate=0.7,
                    )
                    vc_target = vc_target[:, :, ref_mel.size(-1):]
                    wav = tts.bigvgan(vc_target.float()).squeeze().unsqueeze(0)
                    wav = wav.squeeze(1)
                wav = torch.clamp(32767 * wav, -32767.0, 32767.0)

                job.output_path.parent.mkdir(parents=True, exist_ok=True)
                torchaudio.save(str(job.output_path), wav.cpu().type(torch.int16), 22050)
                fit_to_duration(job.output_path, job.target_duration_seconds, ffmpeg_binary=self._ffmpeg)

        wall_seconds = time.monotonic() - t0
        note_stat("tts.gpt_batch_size", len(batchable))
        note_stat("tts.gpt_batch_wall_seconds", round(wall_seconds, 2))
        logger.info(
            "index_tts2.gpt_batch_done",
            batch_size=len(batchable),
            wall_seconds=round(wall_seconds, 2),
        )
