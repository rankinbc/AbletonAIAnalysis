#!/bin/bash

# Ralph Wiggum Loop - AbletonAIAnalysis
# Usage: ./ralph.sh <iterations>
# Example: ./ralph.sh 20

if [ -z "$1" ]; then
  echo "Usage: $0 <iterations>"
  echo "Example: $0 20"
  exit 1
fi

MAX_ITERATIONS=$1
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Ralph Wiggum Loop - AbletonAIAnalysis"
echo "=========================================="
echo "Max iterations: $MAX_ITERATIONS"
echo "Project: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

for ((i=1; i<=$MAX_ITERATIONS; i++)); do
  echo ""
  echo "=========================================="
  echo "  Iteration $i of $MAX_ITERATIONS"
  echo "=========================================="
  echo ""

  # Run Claude with the PROMPT.md content
  result=$(claude -p "$(cat PROMPT.md)" --output-format text 2>&1) || true

  echo "$result"

  # Check for completion signal
  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo ""
    echo "=========================================="
    echo "  ALL TASKS COMPLETE!"
    echo "=========================================="
    echo "Finished after $i iterations."
    exit 0
  fi

  echo ""
  echo "--- End of iteration $i ---"
  echo ""

  # Small delay between iterations to avoid rate limiting
  sleep 2
done

echo ""
echo "=========================================="
echo "  Max iterations reached ($MAX_ITERATIONS)"
echo "=========================================="
echo "Not all tasks may be complete. Check plan.md for status."
exit 1
