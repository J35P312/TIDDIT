import argparse
import os
import itertools

def get_regions(vcf,padding):
    variants={}
    for line in open(vcf):
        if line[0] == "#":
            continue
        if "WINA" in line and "WINB" in line:
            a=line.split("WINA=")[-1].split(";")[0].split(",")
            a[0]=int(a[0])-padding
            if a[0] < 0:
                a[0] =0
                
            a[1]=int(a[1])+padding
            if "CHRA=" in line:
               chra=line.split("CHRA=")[-1].split(";")[0]
            else:
               chra=line.split("\t")[0]
               chrb=chra
            b=line.split("WINB=")[-1].split(";")[0].split(",")
            b[0]=int(b[0])-padding
            if b[0] < 0:
                b[0] =0
            b[1]=int(b[1])+padding
            if "CHRB=" in line:
               chrb=line.split("CHRB=")[-1].split(";")[0]
            
            #the regions should not overlap
            if(chrb == chra and b[0] <= a[1]):
                b[0] = a[1]+1
            variant={"ID":line.split("\t")[2],"startA":a[0],"endA":a[1],"chrA":chra,"startB":b[0],"endB":b[1],"chrB":chrb}
            variants[variant["ID"]]=variant
    
    return variants

def get_sam_data(line):
    content=line.strip().split("\t")
    start=int(content[3])
    end = int(content[3])
    SC = ["".join(x) for _, x in itertools.groupby(content[5], key=str.isdigit)]

    length=0
    for i in range(0,len(SC)/2):
        if SC[i*2+1] == "M":
            length += int( SC[i*2] )
	end+=length
		    
    sam={"ID":content[0],"chr":content[2],"start":start,"end": end,"Q":int(content[4]),"CIGAR":content[5],"length":length}
    return(sam)

parser = argparse.ArgumentParser("""use the sam files and annotated fa files to filter false positives and to update the position of variants, and filter false positives""")
parser.add_argument('--vcf',type=str,required = True,help="the path to the TIDDIT vcf file")
parser.add_argument('--q',type = int,default =0,help="the lowest tolerated mapping quality of a contig(default = 10)")
parser.add_argument('--padding',type = int,default =150,help="the lowest tolerated mapping quality of a contig(default = 150)")
parser.add_argument('--working_dir',required=True,type=str,default="",help="path to the folder containing the bam files of extracted variants")
args, unknown = parser.parse_known_args()

variants=get_regions(args.vcf,args.padding)

for ID in variants:
    variant=variants[ID]
    sam_file=os.path.join( args.working_dir,variant["ID"]+".sam" )
    fa_file=os.path.join( args.working_dir,variant["ID"]+".fa" )
    hit=0;
    miss=0;
    bridge=0
    score=0;
    contigs={}
    if os.path.exists(sam_file):
        for line in open(sam_file):
            if not line[0] == "@":
                contig=get_sam_data(line)
                if contig["Q"] < args.q:
                    continue
                if not contig["ID"] in contigs:
                    contigs[contig["ID"]]=[]
                contigs[contig["ID"]].append(contig)
 
        contigs={}
        for line in open(fa_file):
            if line[0] == ">":
                content=line[1:].strip().split()
                contig_id=content[0]
                contigs[contig_id]["significance"]=content[2].split(":")[2]
                contigs[contig_id]["coverage"]=float( content[1].split(":")[4] )
                contigs[contig_id]["length"]=int( content[1].split(":")[1] )
 
 
                
        failed=0;
        bases_inside_roi=0
        bases_outside_roi=0     
        for cnt in contigs:
            if contigs[cnt]["significance"] == "False":
                failed +=1
                continue
        
            contig=contigs[cnt]
            A=False
            B=False
            for alignment in contig:
            
                if not alignment["chr"] == variant["chrA"] and not alignment["chr"] == variant["chrB"]:
                    miss += 1
                    bases_outside_roi += alignment["length"]*contigs[cnt]["coverage"]
                    
                elif variant["chrB"] == variant["chrA"]:
                    if (alignment["start"] <= variant["endA"] and alignment["end"] >= variant["startA"]) :
                        hit +=1
                        bases_inside_roi += alignment["length"]*contigs[cnt]["coverage"]
                        A=True
                    elif (alignment["end"] >= variant["startB"] and alignment["start"] <= variant["endB"]) :
                        hit +=1
                        bases_inside_roi += alignment["length"]*contigs[cnt]["coverage"]
                        B= True
                    else:
                        miss +=1
                        bases_outside_roi += alignment["length"]*contigs[cnt]["coverage"]
                        
                elif alignment["chr"] == variant["chrA"]:
                    if (alignment["start"] <= variant["endA"] and alignment["end"] >= variant["startA"]) :
                        hit +=1
                        bases_inside_roi += alignment["length"]*contigs[cnt]["coverage"]
                        A=True
                    else:
                        miss +=1
                        bases_outside_roi += alignment["length"]*contigs[cnt]["coverage"]
                else:
                    if (alignment["end"] >= variant["startB"] and alignment["start"] <= variant["endB"]) :
                        hit +=1
                        bases_inside_roi += alignment["length"]*contigs[cnt]["coverage"]
                        B=True
                    else:
                        miss +=1
                        bases_outside_roi += alignment["length"]*contigs[cnt]["coverage"]
                if A and B:
                    bridge += 1;
                    bases_inside_roi += -alignment["length"]*contigs[cnt]["coverage"]
                           
        if hit or miss:
            score=bases_outside_roi/float(bases_inside_roi + bases_outside_roi)
        else:
            score = 0
            
    variants[ID]["hit"]=hit
    variants[ID]["miss"]=miss
    variants[ID]["bridge"]=bridge
    variants[ID]["score"]=score
    
for line in open(args.vcf):
        
    if line[0] == "#":
        if not line[1] == "#" :
            print "##INFO=<ID=HIT,Number=1,Type=Integer,Description=\"The number of contigs that map within one of the windows\">"
            print "##INFO=<ID=BRIDGE,Number=1,Type=Integer,Description=\"The number of contigs that map within both windows\">"
            print "##INFO=<ID=MISS,Number=1,Type=Integer,Description=\"The number of contigs that map outside any window\">"
            print "##INFO=<ID=SCORE,Number=1,Type=Float,Description=\"The assembly score of the variant, 0 is the best score, 1 is the worst\">"
            print "##INFO=<ID=SCORE,Number=2,Type=Integer,Description=\"The number of bases mapping within the region, as well as the numbe rof bases mapping outside\">"
            print "##FILTER=<ID=FAIL,Description=\"The assembly of the variant is too scattered and noisy to consider the variant\">"
        print line.strip()
        continue
            
    hit =0
    bridge =0
    miss = 0
    score =0
    content=line.strip().split("\t")
    if content[2] in variants:
        hit= variants[ content[2] ]["hit"]
        bridge= variants[ content[2] ]["bridge"]
        miss = variants[ content[2] ]["miss"]
        score = variants[ content[2] ]["score"]
                 
            
    content[7] += ";HIT={};BRIDGE={};MISS={};SCORE={};SUPPORTINGBASES={},{}".format(hit,bridge,miss,score,bases_inside_roi,bases_outside_roi)
    if failed == len(contigs):
        content[6] = "FAIL"
    elif score >= 0.30:
        content[6] = "FAIL"
    print "\t".join(content)
        
                                
