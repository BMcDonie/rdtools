from energy_normalization import normalize_with_sapm
from degradation import degradation_ols
from degradation import degradation_classical_decomposition
from degradation import degradation_year_on_year

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
