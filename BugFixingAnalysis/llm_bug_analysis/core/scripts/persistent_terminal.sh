#!/bin/bash

echo "{separator}"
echo "{title}"
echo "{separator}"
echo ""

QUEUE="{queue_file}" # commands to run
DONE="{done_file}" # functions as lock and exit code storage
STOP="{stop_file}"
LOG_MAP="{log_map_file}"

# runs until the stop file is created
while [ ! -f "$STOP" ]; do
    if [ -s "$QUEUE" ]; then # -s: file exists and not empty
        CMD=$(head -n 1 "$QUEUE") # read first line
        tail -n +2 "$QUEUE" > "$QUEUE.tmp" && mv "$QUEUE.tmp" "$QUEUE" # remove first line
        
        if [ ! -z "$CMD" ]; then # got a command, run it
            echo ""
            echo "{divider}"
            echo "$CMD"
            echo "{divider}"
            
            # check if command should be logged
            if [ -f "$LOG_MAP" ]; then
                LOG_FILE=$(cat "$LOG_MAP")
                rm "$LOG_MAP"

                # using script command to keep colors and dynamic output
                mkdir -p "$(dirname "$LOG_FILE")"
                script -q -e -c "$CMD" /dev/null | tee "$LOG_FILE"
                CODE=${{PIPESTATUS[0]}}
            else
                eval "$CMD"
                CODE=$?
            fi
            
            echo ""
            [ $CODE -eq 0 ] && echo "Success" || echo "Failed (exit $CODE)"
            echo "$CODE" > "$DONE"
        fi
    fi
    sleep 0.2
done

echo ""
echo "{separator}"
echo "Pipeline complete! Terminal will close in 10 seconds..."
echo "{separator}"
read -t 10