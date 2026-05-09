#!/bin/bash
# Hook: Warn if a training script is missing random seed (reproducibility risk)

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.py ]]; then exit 0; fi
if [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

# Check training-related files AND preprocess scripts (shuffle also needs seed)
BASENAME=$(basename "$FILE_PATH")
DIRPATH=$(dirname "$FILE_PATH")

IS_SEED_FILE=0
if echo "$BASENAME" | grep -qiE "^train|_train|training|preprocess|preprocessing"; then IS_SEED_FILE=1; fi
if echo "$DIRPATH" | grep -qiE "/train(/|$)|/data(/|$)"; then IS_SEED_FILE=1; fi

if [[ $IS_SEED_FILE -eq 0 ]]; then exit 0; fi

# Check for seed setting
HAS_SEED=0
if grep -qE "random\.seed|np\.random\.seed|torch\.manual_seed|set_seed|SEED\s*=" "$FILE_PATH"; then
  HAS_SEED=1
fi

if [[ $HAS_SEED -eq 0 ]]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"⚠️ Training script missing random seed — results will not be reproducible. Add at top of file:\n  import random, numpy as np, torch\n  SEED = 42\n  random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)"}}'
fi

exit 0
