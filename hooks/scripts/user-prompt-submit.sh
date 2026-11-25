#!/bin/sh
# Reminds Claude to offer a diary entry when the user writes "gem status".
# UserPromptSubmit hooks get JSON on stdin (the user's text is in "prompt")
# and add plain stdout to Claude's context, so no JSON output is needed.
# Uses only POSIX sh + tr + grep, so it runs under Git Bash on Windows and sh on macOS/Linux.
# No jq, no node, no bash-isms: maximum portability across machines.
#
# This hook must never block a prompt: every path ends in exit 0, and a
# parse failure simply means no output.

# Run by hand without piped input: do not wait on the terminal.
if [ -t 0 ]; then
  exit 0
fi

# Match the phrase only inside the string value of the "prompt" key.
#   "prompt" *: *"        a real key: inside any other string value the quotes
#                         would be escaped (\"prompt\"), so this cannot match there
#   [^"\]*(\\.[^"\]*)*    string content up to, never past, the closing quote
#                         (escaped quotes \" and escaped newlines \n are stepped over)
#   gem  *status          the phrase, case-insensitive via grep -i
# tr joins pretty-printed JSON into one line first. LC_ALL=C keeps grep
# byte-based, so odd bytes in the prompt cannot cause a locale error.
if LC_ALL=C tr -d '\n\r' 2>/dev/null |
  LC_ALL=C grep -i -q '"prompt"[[:space:]]*:[[:space:]]*"[^"\\]*\(\\.[^"\\]*\)*gem  *status' 2>/dev/null
then
  echo "[outer_heaven] Brugeren skrev 'gem status'. Når status er gemt i command-deck: stil ét spørgsmål, om der også skal skrives et dagbogsindlæg (diary-skillen) for sessionens arbejde. Skriv ikke dagbogen uden et ja."
fi

exit 0
