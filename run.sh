#!/bin/bash

LOCUS_OPTS="-f locust_async.py"
LOCUST_MODE=${LOCUST_MODE:-standalone}
no_slaves=${NUMBER_SLAVES:-10}
num=${NUM_THREADS_FROM:-1}
req=${NUM_REQUESTS:-1}
tunit=${TIME_UNIT:-m}
treq=$(($num * $req))

	if [[ "$LOCUST_MODE" = "master" ]]; then
		LOCUS_OPTS="$LOCUS_OPTS --no-web --master --expect-slaves $no_slaves -c $num -r $num --csv=$treq --only-summary"
	elif [[ "$LOCUST_MODE" = "worker" ]]; then
		LOCUS_OPTS="$LOCUS_OPTS --no-web --slave --master-host=$LOCUST_MASTER -c $num -r $num"
	fi
locust $LOCUS_OPTS