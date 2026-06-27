# Minimal zsh prompt for clean reterm demo recordings.
# Recordings spawn the user's $SHELL; pointing ZDOTDIR here (via a script's
# `env:`) gives a neutral, plugin-free prompt with no git branch, dirty flag,
# or local path leaking into the GIF/SVG. reterm injects its OSC 133 hooks
# after startup, so they work regardless of this file.
PROMPT=$'%F{green}➜%f  %F{cyan}reterm%f $ '
