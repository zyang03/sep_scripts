#!/bin/tcsh
### first is the common part
###   each node is dual CPU with Quad core Nehalem
#PBS -N jobname
#PBS -l nodes=1:ppn=8
#PBS -q default
#PBS -V
#PBS -m e
#PBS -W x="PARTITION:sw121"
#PBS -j oe
#PBS -e /data/sep/zyang03/proj/RMO/waz3d/wrk
#PBS -o /data/sep/zyang03/proj/RMO/waz3d/wrk
#PBS -d /data/sep/zyang03/proj/RMO/waz3d/wrk
#

#
cd $PBS_O_WORKDIR
#

echo WORKDIR is: $PBS_O_WORKDIR
sleep 5
echo NodeFile is: $PBS_NODEFILE
echo hostname is: $HOSTNAME

set TMPDIR=/tmp
set HOSTFILE=hostfile_${PBS_JOBID}
echo hostfile is: ${HOSTFILE}
cat ${PBS_NODEFILE} | sort | uniq > ${HOSTFILE}


