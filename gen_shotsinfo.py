#!/usr/bin/python
import commands
import sys,re,os,string
import pbs_util
import sepbase

def self_doc():
  print 
  print 

## This program will try to generate a meta information files from a large dataset that contains many small pieces file into small pieces, and do stuff to extract the migration aperture for each files.
# Usage1:    *.py filelist=file_contains_all_file_pieces_names offset=y/n output=output_fn.shotsInfo [path=the_new_path_for_the_file_pieces]
# Usage2:    *.py file=allshots.H offset=y/n output=output_fn.shotsInfo path=the_new_path_for_the_file_pieces]  # This is for 2D case, where the shots are initially binded in one single file nshots_perfile=[10]

if __name__ == '__main__':
  dict_args,args=sepbase.parse_args(sys.argv[1:])
  b3D = True
  if 'filelist' in dict_args:
    fn_flist = dict_args['filelist']
  else:
    fn_allshots = dict_args['file']
    b3D = False
  # Figure out the output shotsInfo filename.
  fn_shotsinfo = dict_args['output']
  if b3D:
    # Read all shot file names into a list.
    fp_i = open(fn_flist,"r")
    shot_files = fp_i.read().strip().split('\n')
    fp_i.close()
  else:  # Figure out how to divide the file to group of shots
    ax_shots = sepbase.get_sep_axis_params(fn_allshots,4)
    N = int(ax_shots[0])
    n = int(dict_args['nshots_perfile'])
    assert N>=n
    ishot_list = range(0,N,n)
    nshot_list = [n]*(len(ishot_list)-1)
    nshot_list.append(N - ishot_list[-1])
    shot_files = []
    _, fn_shots_base, _ = pbs_util.SplitFullFilePath(os.path.abspath(fn_allshots))
    for ish,nsh in zip(ishot_list,nshot_list):
      shot_files.append('%s_%03d_%03d.H' % (fn_shots_base,ish,ish+nsh))

  if "path" in dict_args:
    path = dict_args["path"]
    path = os.path.abspath(path)
  else:
    path = None
    assert b3D == True

  #check if it is marine or land acquistion
  if dict_args["offset"]=="n":
    b_marine = False
  elif dict_args["offset"]=="y":
    b_marine = True
  else:
    err("Specify offset=y/n, to indicate if it is marine or land acquisition!")
  aper_x_extra = 0; aper_y_extra = 0
  if dict_args.has_key("aper_x"): aper_x_extra = float(dict_args["aper_x"])
  if dict_args.has_key("aper_y"): aper_y_extra = float(dict_args["aper_y"])
  
  lines_output = []
  file_cnt = 0
  for file in shot_files:
    if b3D:
      # First check the shot file is valid
      fe = pbs_util.CheckSephFileError(file, check_binary=True)
      assert fe == 0, "file %s is invalid: %d!" % (file, fe)
      if path is None:
        file_name_full = os.path.abspath(file)
      else:
        file_name_full = "%s/%s" % (path, os.path.basename(file))
        sepbase.RunShellCmd("Cp %s %s datapath=%s/" % (file, file_name_full, path))
    else:  # Use window3d to create individual shots file.
        file_name_full = "%s/%s" % (path, file)
        ish = ishot_list[file_cnt]
        nsh = nshot_list[file_cnt]
        sepbase.RunShellCmd('Window3d n4=%d f4=%d squeeze=n <%s >%s out=%s@' % (nsh,ish, fn_allshots, file_name_full, file_name_full),True,True)
    assert pbs_util.CheckSephFileError(file_name_full)==0, "%s output file is not valid !!! Check file fname_out2!" % file_name_full
    # read in that files dimension
    his_eachshot={}
    sepbase.get_sep_axes_params(file_name_full,his_eachshot,"g")
    ogx = float(his_eachshot["og_1"]); ngx=int(his_eachshot["ng_1"]); dgx=float(his_eachshot["dg_1"])
    osx = float(his_eachshot["og_4"]); nsx=int(his_eachshot["ng_4"]); dsx=float(his_eachshot["dg_4"])
    if b3D:
      ogy = float(his_eachshot["og_2"]); ngy=int(his_eachshot["ng_2"]); dgy=float(his_eachshot["dg_2"])
      osy = float(his_eachshot["og_5"]); nsy=int(his_eachshot["ng_5"]); dsy=float(his_eachshot["dg_5"])
    else:
      ogy = 0; ngy = 1; dgy = 1.0
      osy = 0; nsy = 1; dsy = 1.0
    sx_max = osx+(nsx-1)*dsx; sy_max = osy+(nsy-1)*dsy
    gx_max = ogx+(ngx-1)*dgx; gy_max = ogy+(ngy-1)*dgy
    #Calculate the migration aperture based on the src/recv locations
    if (b_marine):
      xmin = min(osx+ogx,osx)
      xmax = max(sx_max,sx_max+gx_max)
      ymin = min(osy+ogy,osy);
      ymax = max(sy_max,sy_max+gy_max)
    else:
      xmin = min(osx,ogx)
      xmax = max(sx_max,gx_max)
      ymin = min(osy,ogy);
      ymax = max(sy_max,gy_max)
    # If there is extra aperture added.
    xmin -= aper_x_extra; xmax += aper_x_extra
    ymin -= aper_y_extra; ymax += aper_y_extra
    lines_output.append("%s %5.3f %5.3f %5.3f %5.3f" % (file_name_full,xmin,xmax,ymin,ymax))
    file_cnt += 1
    print "file_cnt=%d" % file_cnt
  # End for file in shot_files
  # Now write out the first two lines of file.
  offset = "y"
  if not b_marine: offset = "n"
  line1 = "%d bMarineGeom=%s singleSrcFileForAllShots=y \n" % (file_cnt,offset)
  line2 = "fname_data xmin xmax ymin ymax \n"
  fp_o = open(fn_shotsinfo,"w")
  fp_o.write(line1+line2)
  fp_o.writelines("\n".join(lines_output))
  fp_o.write("\n")
  fp_o.close()

