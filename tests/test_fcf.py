from decimal import Decimal
from app.utils import build_fcf_text

def test_fcf_builder_position_mmc_datums():
    f = build_fcf_text('position', Decimal('0.2'), 'mm', True, 'MMC', ['A','B','C'])
    assert '⌀0.2 mm' in f
    assert 'Ⓜ' in f
    assert 'A' in f and 'B' in f and 'C' in f
