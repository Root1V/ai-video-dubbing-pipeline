from __future__ import annotations

import torch

from video_translator.infrastructure.synthesis.index_tts2_synthesizer import _split_batched_codes

_STOP = 8193


def test_each_item_gets_its_own_row_not_always_row_zero():
    """Regresion: una version anterior devolvia siempre la fila 0 para todos
    los items del batch (solo el largo del recorte variaba por item), asi
    que el batch entero terminaba sonando con el contenido del primer item."""
    codes = torch.tensor(
        [
            [1, 2, 3, _STOP, _STOP],
            [10, 20, _STOP, _STOP, _STOP],
            [100, 200, 300, 400, _STOP],
        ]
    )

    result = _split_batched_codes(codes, _STOP)

    assert len(result) == 3
    assert result[0].tolist() == [[1, 2, 3]]
    assert result[1].tolist() == [[10, 20]]
    assert result[2].tolist() == [[100, 200, 300, 400]]


def test_row_without_any_stop_token_keeps_full_length():
    codes = torch.tensor([[1, 2, 3, 4]])
    result = _split_batched_codes(codes, _STOP)
    assert result[0].tolist() == [[1, 2, 3, 4]]


def test_degenerate_immediate_stop_yields_empty_tensor_not_the_stop_token():
    """Regresion: si el primer token generado YA es el stop_mel_token
    (code_len=0), el resultado debe ser un tensor VACIO (1, 0) -- igual que
    infer_generator para el caso analogo de un solo item -- no un tensor con
    el stop_mel_token en si, que excede el vocabulario del codec semantico
    y causaba un IndexError al intentar decodificarlo como codigo real."""
    codes = torch.tensor([[_STOP, _STOP, _STOP]])
    result = _split_batched_codes(codes, _STOP)
    assert result[0].shape == (1, 0)
