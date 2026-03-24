from operator_use.agent.tools.builtin.filesystem import read_file,write_file,edit_file,list_dir
from operator_use.agent.tools.builtin.patch import patch_file
from operator_use.agent.tools.builtin.web import web_search,web_fetch
from operator_use.agent.tools.builtin.terminal import terminal
from operator_use.agent.tools.builtin.message import intermediate_message, react_message, send_file
from operator_use.agent.tools.builtin.cron import cron
from operator_use.agent.tools.builtin.subagents import subagents
from operator_use.agent.tools.builtin.process import process
from operator_use.agent.tools.builtin.channel import channel
from operator_use.agent.tools.builtin.acp_agents import acpagents
from operator_use.agent.tools.builtin.local_agents import localagents
from operator_use.agent.tools.builtin.control_center import control_center

FILESYSTEM_TOOLS = [read_file,write_file,edit_file,list_dir,patch_file]
WEB_TOOLS = [web_search,web_fetch]
TERMINAL_TOOLS = [terminal]
MESSAGE_TOOLS = [intermediate_message, react_message, send_file]
CRON_TOOLS = [cron]
PROCESS_TOOLS = [process, control_center]
OTHER_AGENT_TOOLS = [subagents,acpagents,localagents]
CHANNEL_TOOLS = [channel]

AGENT_TOOLS = FILESYSTEM_TOOLS + WEB_TOOLS + TERMINAL_TOOLS + CRON_TOOLS + PROCESS_TOOLS + OTHER_AGENT_TOOLS

NON_AGENT_TOOLS = MESSAGE_TOOLS + CHANNEL_TOOLS

__all__ = ["AGENT_TOOLS", "NON_AGENT_TOOLS"]
