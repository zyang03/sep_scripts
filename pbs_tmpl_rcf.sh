#!/bin/tcsh
### first is the common part
###   each node is Quad CPU with Quad core
#PBS -N jobname
#PBS -l nodes=1:ppn=16
#PBS -q default
#PBS -V
#PBS -m e
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

#set TMPDIR=/tmp
#set HOSTFILE=hostfile_${PBS_JOBID}
#echo hostfile is: ${HOSTFILE}
#cat ${PBS_NODEFILE} | sort | uniq > ${HOSTFILE}
#set MIG_PAR_WAZ3D=" pdip=65 oper=ssfpi nvrf=4 nws=32 nxpad_beg=40 nxpad_end=40 nypad_beg=30 nypad_end=30 ntpx=25 ntpy=25 memchk=n "
#image_zmin=10 image_zmax= "


