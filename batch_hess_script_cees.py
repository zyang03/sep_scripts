#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os
from sepbase import *

tangbin="/data/sep/zyang03/other/yaxun_weo/bin"
ybin="/data/sep/zyang03/bin"

def self_doc():
  print 
  print 
  print 
  print 
  print 

## This program will try to batch generate diag hessian computing diagrams
# Usage1:    *.py pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 nbatch=?
# Usage2:		 User can also supply a list of ish_begs to start with
#						 *.py pbs_script_tmpl.sh nfiles=1001 path=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beglist=? nfiles_perbatch=10 csou=csou.H

eq_args,args=parse_args(sys.argv[1:])
fname_tmpl_script = args[0] #assume the target file name is the first argument
#separate the files and path
base = os.path.basename(fname_tmpl_script); base_wo_ext = os.path.splitext(base)[0]

path_out = "."; prefix = "hess-waz3d"

n=0;N=0
if eq_args.has_key("nfiles"):
	N=int(eq_args["nfiles"])
else:
	err("specify nfiles!!!")
if eq_args.has_key("nfiles_perbatch"):
	n=int(eq_args["nfiles_perbatch"])
else:
	err("specify nfiles_perbatch!!!")

fn_csou = "csou3d-j6.H"
if eq_args.has_key("csou"):
	fn_csou=(eq_args["csou"])
else:
	err("specify csou!!!")
fn_csou = os.path.abspath(fn_csou)

if eq_args.has_key("path"):
	path_out = eq_args["path"]
else:
	path_out = os.getcwd() #use the default, the current directory
if eq_args.has_key("prefix"):
	prefix = eq_args["prefix"]

queue = "default"
if eq_args.has_key("queue"):
	queue = eq_args["queue"]

nnodes = 0
if eq_args.has_key("nnodes"):
	nnodes = int(eq_args["nnodes"])
if eq_args.has_key("prefix-img"):
	prefix = eq_args["prefix"]

njob_max = 1
if eq_args.has_key("njobmax"):
	njob_max = int(eq_args["njobmax"])
print "njob_max=%d"%(njob_max)

##Learn the velocity file and the shotsInfo file
fn_v3d = ""; fn_shotsInfo = ""
if eq_args.has_key("vel"):
	fn_v3d				= (eq_args["vel"])
else:
	err("!Missing vel=")
if eq_args.has_key("shotsInfo"):
	fn_shotsInfo	= (eq_args["shotsInfo"])
else:
	err("!Missing shotsInfo")

bInputFileList = False
ish_start = 0; ish_flist = ""
ishotLists = []
b_ish_beg			= eq_args.has_key("ish_beg"); b_ish_beglist = eq_args.has_key("ish_beglist")

if b_ish_beg and b_ish_beglist:
	err("!!! cannot have both: ish_beg & ish_beglist")
if (not b_ish_beg) and (not b_ish_beglist):
	err("! Need to supply one of the two: ish_beg or ish_beglist!!")

#if shots are grouped by shot_n1 amount, which means when dividing the shots for each job, don't cross the shot_n1 boundary
b_shot_n1_bnd = eq_args.has_key("shot_n1_bnd")
shot_n1_bnd = 0
if (b_shot_n1_bnd):
	shot_n1_bnd = int(eq_args["shot_n1_bnd"])

if b_ish_beg:
	ish_start = int(eq_args["ish_beg"])
	bInputFileList = False
	if (not b_shot_n1_bnd):
		ishotLists = range(ish_start,N,n)
	else: #divide the job such that it did not cross the n1 bnd
		nearest_shot_n1_mult = (ish_start / shot_n1_bnd + 1) * shot_n1_bnd
		ishotLists = range(ish_start,min(nearest_shot_n1_mult,N),n)
		if (N>nearest_shot_n1_mult):
			for ii in range(nearest_shot_n1_mult,N,shot_n1_bnd):
				ishotLists += range(ii,min(N,ii+shot_n1_bnd),n)

if b_ish_beglist:
	ish_flist = eq_args["ish_beglist"]
	bInputFileList = True
	# read the list files to generate a list of shots
	fp_list = open(ish_flist,'r')
	line = ""
	while 1:
		line = fp_list.readline();
		if not line:
			break
		else: ## turn this line into a number, ascii 10 is linefeed
			if line != "" and line != chr(10):
				#print "line=",line; print ord(line[-1]), len(line)
				ishotLists.append(int(line))

nbatch = N #set nbatch to be big enough
if eq_args.has_key("nbatch"):
	if (eq_args["nbatch"] != ""):
		nbatch = int(eq_args["nbatch"])
print "ish_start=%d : ish_flist="%ish_start,ish_flist," : nbatch=%d"%nbatch

path_out = os.path.abspath(path_out) #get the absolut path
status = -1
cmd1 = ""; cmd2 = ""
fp_o = []; sz_shotrange = ""

len_shotlist = len(ishotLists)
print len_shotlist,"ishotLists=", ishotLists[0:min(len_shotlist,nbatch)]
njob = 0; ibatch=0

#see if specify image/Hessian dimensions in cmdline
b_cmdl_imgx = eq_args.has_key("xs")
b_cmdl_imgy = eq_args.has_key("ys")
b_cmdl_imgz = eq_args.has_key("zs")
xmin_cmdl = xmax_cmdl = ymin_cmdl = ymax_cmdl = zmin_cmdl = zmax_cmdl = 0.
if b_cmdl_imgx:
	str_list = eq_args["xs"].split(",")
	xmin_cmdl = float(str_list[0]); xmax_cmdl = float(str_list[1])
if b_cmdl_imgy:
	str_list = eq_args["ys"].split(",")
	ymin_cmdl = float(str_list[0]); ymax_cmdl = float(str_list[1])
if b_cmdl_imgz:
	str_list = eq_args["zs"].split(",")
	zmin_cmdl = float(str_list[0]); zmax_cmdl = float(str_list[1])
print "cmdl_xs,ys,zs", xmin_cmdl,xmax_cmdl,ymin_cmdl,ymax_cmdl,zmin_cmdl,zmax_cmdl

path_tmp = "/data/sep/zyang03/proj/RMO/tmp"
for ish in ishotLists:
	ibatch = ibatch + 1
	if (ibatch > nbatch):
		break
	nsh = min(N-ish,n)
	if (b_shot_n1_bnd):
		nearest_shot_n1_mult = (ish / shot_n1_bnd + 1) * shot_n1_bnd
		#print "nearest_shot_n1_mult=%d, nsh=%d,ish=%d, ishd=%d"%(nearest_shot_n1_mult, nsh,ish, ish/shot_ni_bnd)
		nsh = min(nsh, nearest_shot_n1_mult-ish)

	sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
	fn_script = '%s/%s.%s'	%(path_out,base,sz_shotrange)
	fn_log = '%s/%s-%s.log'	%(path_out,prefix,sz_shotrange)
	fnt_hess_list = []
	fnt_bvel = '%s/vel-%s.H' % (path_tmp,sz_shotrange)
	fn_hess  = "%s/%s-%s.H"	%(path_out,prefix,sz_shotrange)

	#construct the pbs script
	cmd1 = "cp %s %s"%(fname_tmpl_script,fn_script)
	print "\nibatch=%d ;"%ibatch,cmd1
	if (os.system(cmd1) != 0):	err( "! Status is %d !"%(status))
	if (queue!=""): #need to change the queue name
		cmd1 = "sed -i 's/#PBS\ -q\ default/#PBS\ -q\ %s/g'   %s"%(queue,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
	if (nnodes!=0): #need to change the number of nodes 
		cmd1 = "sed -i 's/#PBS\ -l\ nodes=1/#PBS\ -l\ nodes=%d/g'   %s"%(nnodes,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
	##redirect PBS output #, change the entire PBS -o line
	cmd1 = "sed -i '/#PBS -o/c\#PBS -o %s' %s"%(fn_log,fn_script)
	cmd2 = "sed -i '/#PBS -e/c\#PBS -e %s' %s"%(fn_log,fn_script)
	if (os.system(cmd1) != 0 or os.system(cmd2) !=0 ):	
		print line_no();
		err( "! Status is %d !"%(status))

	#Append commands to the bottom of the copied script file
	fp_o = open(fn_script,'a')

	fnt_csou = "csou-%04d.H"%ish; fnt_gsou = "gsou-%04d.H"%ish
	#these files does not vary for each invididual shot
	#Cp the bvelocity to local as well
	cmd1 = "Cp <%s | Window3d >%s datapath=${TMPDIR}/"%(fn_csou,fnt_csou)
	cmd2 = "Cp <%s >%s datapath=${TMPDIR}/"%(fn_csou,fnt_gsou)
	cmd3 = "Cp <%s >%s datapath=${TMPDIR}/"%(fn_v3d,fnt_bvel)
	fp_o.write(cmd1+"\n"+cmd2+"\n"+cmd3+"\n")
	
	xmin_g=xmax_g=ymin_g=ymax_g=0
	#do nfiles at once
	for ii in range(0,nsh):
		ishl = ish+ii
		#first find the filename in the shotInfoFile, and extract the receiver geometry
		cmd = "sed -n -e %dp %s"%(ishl+3,fn_shotsInfo)
		stat1,out1 = commands.getstatusoutput(cmd)
		if (stat1 !=0): err(line_no())
		str_lists = out1.split(" "); fn_shotfile = str_lists[0]
	
		print "fn_shotfile=",fn_shotfile
		his_eachshot = {}; get_sep_params(fn_shotfile,his_eachshot,"g")
		ogx = float(his_eachshot["og_1"]); ngx=int(his_eachshot["ng_1"]); dgx=float(his_eachshot["dg_1"])
		ogy = float(his_eachshot["og_2"]); ngy=int(his_eachshot["ng_2"]); dgy=float(his_eachshot["dg_2"])
		osx = float(his_eachshot["og_4"]); nsx=int(his_eachshot["ng_4"]); dsx=float(his_eachshot["dg_4"])
		osy = float(his_eachshot["og_5"]); nsy=int(his_eachshot["ng_5"]); dsy=float(his_eachshot["dg_5"])
	
		# Generate random-phase encoding
		fnt_grec = "grec-random-%04d.H"%(ishl)
		cmd1 = "%s/generate_randomY.x soufnc=%s output=%s datapath=${TMPDIR}/ ngx=%d ngy=%d dgx=%f dgy=%f ogx=%f ogy=%f nsx=%d nsy=%d dsx=%f dsy=%f osx=%f osy=%f iseed=%d "%(tangbin,fnt_csou,fnt_grec,ngx,ngy,dgx,dgy,ogx,ogy,nsx,nsy,dsx,dsy,osx,osy,ishl+1)
		fp_o.write("echo " + cmd1 + " \n");
		fp_o.write("time "+cmd1+"\n\n")
	
		xmin_1 = float(str_lists[1]); xmax_1 = float(str_lists[2])
		ymin_1 = float(str_lists[3]); ymax_1 = float(str_lists[4])
		# Find the overlap between 1shot imaging domain and the final imaging domain
		if b_cmdl_imgx:
			xmin_1 = max(xmin_1,xmin_cmdl); xmax_1 = min(xmax_1,xmax_cmdl)
		if b_cmdl_imgy:
			ymin_1 = max(ymin_1,ymin_cmdl); ymax_1 = min(ymax_1,ymax_cmdl)

		fnt_hess = '%s/%s-%04d.H' % (path_tmp,prefix,ishl); fnt_hess_list.append(fnt_hess)
		#calculate the Hessian matrix
		cmd2 = "%s/bwi-peh3d.x ${MIG_PAR_WAZ3D} ${PAR_HESS} mode=hesian gsou=%s grec=%s sfnc=%s datapath=${TMPDIR}/ memchk=n report=y hess=%s bvel=%s "%(tangbin,fnt_gsou,fnt_grec,fnt_csou,fnt_hess,fnt_bvel)
		cmd2 += " image_xmin=%.1f image_xmax=%.1f image_ymin=%.1f image_ymax=%.1f " % (xmin_1,xmax_1,ymin_1,ymax_1)
		if b_cmdl_imgz:
			cmd2 += " image_zmin=%.1f image_zmax=%.1f " % (zmin_cmdl,zmax_cmdl)
		fp_o.write("echo " + cmd2+ "\n")
		fp_o.write("time " + cmd2+"\n\n")
		
		if (ii==0):
			xmin_g = xmin_1; xmax_g = xmax_1
			ymin_g = ymin_1; ymax_g = ymax_1
		else:
			xmin_g = min(xmin_1,xmin_g); xmax_g = max(xmax_g,xmax_1)
			ymin_g = min(ymin_1,ymin_g); ymax_g = max(ymax_g,ymax_1)
	
	#Now copy the cubes out, if multiple shots then combine them first
	if (n==1):
		cmd1 = "Cp <%s >%s\n"%(fnt_hess,fn_hess)
	else:
		fn_tflist = "%s/%s-%s.flist"%(path_out,prefix,sz_shotrange)
		fp_tflist = open(fn_tflist,"w")
		fp_tflist.write("\n".join(fnt_hess_list))
		fp_tflist.close()
		#axis 3,4,5 are (x,y,z)
		cmd1 = "%s/Combine.x <%s filelist=%s oe3=%f,%f oe4=%f,%f output=%s ndim=5 \n"%(ybin,fnt_hess,fn_tflist,xmin_g,xmax_g,ymin_g,ymax_g,fn_hess)
	
	fp_o.write(cmd1)
	
	#last step, remove the files at tmp folder
	cmd2 = "\n find /tmp/ -maxdepth 1 -type f -user zyang03 -exec rm {} \\;" ;
	fp_o.write(cmd2+"\n")
	fp_o.close()
	#submit the job script to pbs system by looking at if there are enough running jobs
	#err("")

	jobC = 0; jobR = 0; jobQ = 0
	while 1:
		print "starting on ishot: ", ish
		stat1,out1=commands.getstatusoutput('qstat | grep zyang03 | grep \' C \' | wc -l ')
		
		cmd1 = "qstat | grep zyang03 | grep \' R \' | grep %s| wc -l "%(queue)
		stat2,out2=commands.getstatusoutput(cmd1)
		cmd1 = "qstat | grep zyang03 | grep \' Q \' | grep %s| wc -l "%(queue)
		stat3,out3=commands.getstatusoutput(cmd1)
		jobC = int(out1); jobR = int(out2); jobQ = int (out3)
		print jobC," ",jobR,' ',jobQ
		njob = jobR + jobQ
		if (njob < njob_max): #submit a new job
			cmd1 = "qsub %s" % (fn_script)
			print line_no(),": submitting a new job",cmd1
			os.system(cmd1); os.system("sleep 1")
			break
		else:
			print "waiting on the pbs queue"
		os.system("sleep 180") #sleep 3mins before do the query again

	print "ish=",ish, nsh, N

