#!/usr/bin/env bash

set -e

# Default settings
ENABLE_WEBSERVER=1
ENABLE_TASKEXECUTOR=1
CONSUMER_NO_BEG=0
CONSUMER_NO_END=0
WORKERS=1
HOST_ID=$(hostname)

# PID storage
PIDS=()

# Cleanup function
cleanup() {
    echo "Stopping all services..."

    # Kill all background processes started by this script
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Killing process $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done

    # Kill any remaining ragflow_server processes
    pkill -f "ragflow_server.py" 2>/dev/null || true

    # Kill any remaining task_executor processes
    pkill -f "task_executor.py" 2>/dev/null || true

    echo "All services stopped."
    exit 0
}

# Function to kill existing services
kill_existing_services() {
    echo "Cleaning up existing services..."

    # Kill existing ragflow_server processes
    if pgrep -f "ragflow_server.py" > /dev/null; then
        echo "Stopping existing ragflow_server processes..."
        pkill -f "ragflow_server.py" || true
        sleep 2
    fi

    # Kill existing task_executor processes
    if pgrep -f "task_executor.py" > /dev/null; then
        echo "Stopping existing task_executor processes..."
        pkill -f "task_executor.py" || true
        sleep 2
    fi

    echo "Cleanup completed."
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Parse arguments
for arg in "$@"; do
  case $arg in
    --disable-webserver)
      ENABLE_WEBSERVER=0
      shift
      ;;
    --disable-taskexecutor)
      ENABLE_TASKEXECUTOR=0
      shift
      ;;
    --consumer-no-beg=*)
      CONSUMER_NO_BEG="${arg#*=}"
      shift
      ;;
    --consumer-no-end=*)
      CONSUMER_NO_END="${arg#*=}"
      shift
      ;;
    --workers=*)
      WORKERS="${arg#*=}"
      shift
      ;;
    --host-id=*)
      HOST_ID="${arg#*=}"
      shift
      ;;
    --stop)
      echo "Stopping all KnowFlow services..."
      pkill -f "ragflow_server.py" 2>/dev/null || true
      pkill -f "task_executor.py" 2>/dev/null || true
      echo "All services stopped."
      exit 0
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --disable-webserver       Disable ragflow webserver"
      echo "  --disable-taskexecutor    Disable task executor"
      echo "  --consumer-no-beg=N       Consumer ID begin (default: 0)"
      echo "  --consumer-no-end=N       Consumer ID end (default: 0)"
      echo "  --workers=N               Number of worker processes (default: 1)"
      echo "  --host-id=ID              Host identifier (default: hostname)"
      echo "  --stop                    Stop all running services"
      echo "  --help, -h                Show this help message"
      echo ""
      echo "To stop services: Ctrl+C or run: $0 --stop"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Function to run task executor
function task_exe() {
    local consumer_id="$1"
    local host_id="$2"

    if command -v pkg-config &> /dev/null && pkg-config --exists jemalloc; then
        JEMALLOC_PATH="$(pkg-config --variable=libdir jemalloc)/libjemalloc.so"
        echo "Starting task executor ${host_id}_${consumer_id} with jemalloc..."
        while true; do
            LD_PRELOAD="$JEMALLOC_PATH" python rag/svr/task_executor.py "${consumer_id}"
        done
    else
        echo "Starting task executor ${consumer_id} without jemalloc..."
        while true; do
            python rag/svr/task_executor.py "${consumer_id}"
        done
    fi
}

# Clean up existing services before starting
kill_existing_services

# Start components
if [[ "${ENABLE_WEBSERVER}" -eq 1 ]]; then
    echo "Starting ragflow_server..."
    python api/ragflow_server.py &
    PIDS+=($!)
fi

if [[ "${ENABLE_TASKEXECUTOR}" -eq 1 ]]; then
    if [[ "${CONSUMER_NO_END}" -gt "${CONSUMER_NO_BEG}" ]]; then
        echo "Starting task executors on host '${HOST_ID}' for IDs in [${CONSUMER_NO_BEG}, ${CONSUMER_NO_END})..."
        for (( i=CONSUMER_NO_BEG; i<CONSUMER_NO_END; i++ ))
        do
          task_exe "${i}" "${HOST_ID}" &
          PIDS+=($!)
        done
    else
        echo "Starting ${WORKERS} task executor(s) on host '${HOST_ID}'..."
        for (( i=0; i<WORKERS; i++ ))
        do
          task_exe "${i}" "${HOST_ID}" &
          PIDS+=($!)
        done
    fi
fi

# Show running services
echo "Services started with PIDs: ${PIDS[*]}"
echo "To stop all services: Ctrl+C or run: $0 --stop"

wait