#!/bin/bash

PID=$(lsof -t -i :5000)

if [ -z "$PID" ]; then
  echo "No process is running on port 5000."
else
  echo "Killing process $PID running on port 5000."
  kill -9 $PID
fi

PID=$(lsof -t -i :3000)

if [ -z "$PID" ]; then
  echo "No process is running on port 5000."
else
  echo "Killing process $PID running on port 5000."
  kill -9 $PID
fi


# Navigate to the backend and start the backend service
cd backend
source myenv/bin/activate
echo "Starting Backend..."
python3 app.py &

# Navigate to the frontend and start the frontend service
cd ../frontend
echo "Starting Frontend..."
npm run dev &

# Wait for both processes to complete
wait
