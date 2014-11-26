#!/bin/tcsh
set DIF = /usr/bin/gvimdiff
set L = $7
set R = $6

echo $DIF $L $R
$DIF $L $R

