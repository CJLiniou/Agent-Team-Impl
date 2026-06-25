"""RunStrategy — 编码执行策略（策略模式）。

每个策略实现一种运行模式：simple / team / custom_team。
"""

from .base import RunStrategy
from .simple_strategy import SimpleStrategy
from .team_strategy import TeamStrategy
from .custom_team_strategy import CustomTeamStrategy
