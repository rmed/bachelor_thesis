#!/bin/bash

function err() {
    echo "--- Error ---"
    echo $@
    echo
    exit 1
}

which python3 > /dev/null || err "Please install python3"

. etc/environment.sh

export ZOE_HOME=$(pwd)
export ZOE_LOGS=${ZOE_HOME}/logs
export ZOE_VAR=${ZOE_HOME}/var
export ZOE_DOMAIN=private
export PYTHONUNBUFFERED=1
export PERL5LIB=${ZOE_HOME}/lib/perl:${PERL5LIB}

#
# Starts the outpost
# Returns its PID
#
function launch_outpost() {
    export PYTHONPATH=${ZOE_HOME}/lib/python-dependencies:${ZOE_HOME}/lib/python:${PYTHONPATH}
    python3 outpost/outpost.py > ${ZOE_LOGS}/outpost.log 2>&1 &
    echo $!
}

#
# Starts an agent
#   launch_agent [name]
# Writes the PID into 'var/agent.pid' file
#
function launch_agent() {
    name="$1"

    AGENTDIR=${ZOE_HOME}/agents/$name
    pushd $AGENTDIR > /dev/null 2>&1

    export PYTHONPATH=${ZOE_HOME}/lib/python-dependencies:${ZOE_HOME}/lib/python:${AGENTDIR}/lib:${PYTHONPATH}

    if [[ -f "pip-requirements.txt" ]] && [[ ! -f ".pip-requirements-installed" ]]
    then
        echo "Installing pip requirements for $name"
        mkdir -p lib
        pip3 install -t lib -r pip-requirements.txt && touch .pip-requirements-installed && echo "Done!"
    fi

    for script in *
    do
        if [[ -f "$script" ]] && [[ -x "$script" ]]
        then
            echo "Launching agent $name ($script)..."
            ./${script} > ${ZOE_LOGS}/$name.log 2>&1 &
            sleep 1
        fi
    done
    popd > /dev/null 2>&1

    echo "$!" > ${ZOE_VAR}/$name.pid
}

#
# Restarts an agent
# restart_agent [name]
#
function restart_agent() {
    name="$1"

    stop_agent $name
    launch_agent $name
}

#
# Starts the outpost
#
function outpost() {
    echo "Starting outpost..."
    launch_outpost > ${ZOE_VAR}/outpost.pid
    sleep 5
}

#
# Starts your beautiful Zoe agents
#
function start() {
    echo "Starting agents..."
    pushd ${ZOE_HOME}/agents > /dev/null 2>&1
    for f in *
    do
        if [[ -d "$f" ]]
        then
            popd >/dev/null 2>&1
            launch_agent $f
            pushd ${ZOE_HOME}/agents > /dev/null 2>&1
        fi
    done
    popd >/dev/null 2>&1
}

#
# Stops your ZOE instance
#
function stop() {
    for f in ${ZOE_VAR}/*.pid
    do
        if [[ -f "$f" ]]
        then
            pid=$(cat $f)
            echo "Stopping process $pid ($f)"
            kill "$pid"
            rm "$f"
        fi
    done
}

#
# Stops a single Zoe agent
# stop_agent [name]
#
function stop_agent() {
    name="$1"
    f="${ZOE_VAR}/$name.pid"

    if  [[ -f "$f" ]]
    then
        pid=$(cat $f)
        echo "Stopping process $pid ($f)"
        kill "$pid"
        rm "$f"
    fi
}

#
# Shows the zoe running processes
#
function status() {
  for f in ${ZOE_VAR}/*.pid
  do
      if [[ -f "$f" ]]
      then
          name=$(basename $f)
          name=${name%%.pid}
          pid=$(cat $f)
          found=$(ps -p $pid)
          r=$?
          if [[ "$r" == "0" ]]
          then
            echo "ALIVE $name (pid $pid)"
          else
            echo "DEAD! $name"
          fi
      fi
  done
}

#
# Launches a python shell with the zoe libs and their dependencies loaded
#
function launch_python_shell() {
  TMP=/tmp/zoe_shell.py
  echo "
import zoe
import os
import sys
import pprint
" > $TMP
  echo "Launching python3 interactive shell with path $PYTHONPATH"
  PYTHONSTARTUP=$TMP python3
}

#
# Magic starts here
#   ./zoe.sh [start | stop]
#
case "$1" in
  "start" )
    outpost
    start
    ;;
  "stop" )
    stop
    ;;
  "status" )
    status
    ;;
  "restart" )
    stop
    outpost
    start
    ;;
  "launch-agent" )
    launch_agent "$2"
    ;;
  "stop-agent" )
    stop_agent "$2"
    ;;
  "restart-agent" )
    restart_agent "$2"
    ;;
  "python" )
    launch_python_shell
    ;;
  * )
    echo "usage: ./outpost.sh start | stop | status | restart | launch-agent <name> | stop-agent <name> | restart-agent <name> | python"
    ;;
esac
