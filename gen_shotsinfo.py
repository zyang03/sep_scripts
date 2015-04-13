#!/usr/bin/python
import commands
import sys,re,os,string
import pbs_util
import sepbase

def self_doc():
  print 
  print 

## This program will try to generate a meta information files from a large dataset that contains many small pieces file into small pieces, and do stuff to extract the migration aperture for each files.
# Usage:    *.py filelist=file_contains_all_file_pieces_names offset=y/n output=output_fn.shotsInfo [path=the_new_path_for_the_file_pieces]

if __name__ == '__main__':
  dict_args,args=sepbase.parse_args(sys.argv[1:])
  fn_flist = dict_args['filelist']
  # Figureout the output shotsInfo filename.
  fn_shotsinfo = dict_args['output']
  # Read all shot file names into a list.
  fp_i = open(fn_flist,"r")
  shot_files = fp_i.read().strip().split('\n')
  fp_i.close()
  if "path" in dict_args:
    path = dict_args["path"]
    path = os.path.abspath(path)
  else:
    path = None
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
    # First check the shot file is valid
    fe = pbs_util.CheckSephFileError(file, check_binary=True)
    assert fe == 0, "file %s is invalid: %d!" % (file, fe)
    if path is None:
      file_name_full = os.path.abspath(file)
    else:
      file_name_full = "%s/%s" % (path, os.path.basename(file))
      sepbase.RunShellCmd("Cp %s %s datapath=%s/" % (file, file_name_full, path))
    assert os.path.exists(file_name_full), "%s does not exist!!! Check file fname_out2!" % file_name_full
    #read in that files dimension
    his_eachshot={}
    sepbase.get_sep_axes_params(file_name_full,his_eachshot,"g")
    #need to extract the dimension information from each shot
    ogx = float(his_eachshot["og_1"]); ngx=int(his_eachshot["ng_1"]); dgx=float(his_eachshot["dg_1"])
    ogy = float(his_eachshot["og_2"]); ngy=int(his_eachshot["ng_2"]); dgy=float(his_eachshot["dg_2"])
    gx_max = ogx+(ngx-1)*dgx; gy_max = ogy+(ngy-1)*dgy
    
    file_cnt += 1
    #Calculate the migration aperture based on the src/recv locations
    xmin = ogx;    xmax = gx_max
    ymin = ogy;    ymax = gy_max
    # If there is extra aperture added.
    xmin -= aper_x_extra; xmax += aper_x_extra
    ymin -= aper_y_extra; ymax += aper_y_extra
    lines_output.append("%s %5.3f %5.3f %5.3f %5.3f" % (file_name_full,xmin,xmax,ymin,ymax))
    print "%d: %s" % (file_cnt, lines_output[file_cnt-1])
  
  # Now write out the first two lines of file.
  offest = "y"
  if not b_marine: offset = "n"
  line1 = "%d bMarineGeom=%s singleSrcFileForAllShots=y \n" % (file_cnt,offset)
  line2 = "fname_data xmin xmax ymin ymax \n"
  fp_o = open(fn_shotsinfo,"w")
  fp_o.write(line1+line2)
  fp_o.writelines("\n".join(lines_output))
  fp_o.write("\n")
  fp_o.close()

