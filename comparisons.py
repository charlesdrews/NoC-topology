#!/usr/bin/python
import sys
import subprocess
import re
import writeconfigs as wc

def check_args(argv = sys.argv):
    # check if target program provided on command line
    if ( len(sys.argv) < 5 or
         int(sys.argv[1]) < 9 or
         int(sys.argv[2]) < 4 or
         str(sys.argv[3]) not in ['novel', 'ring', 'mesh', 'torus']
    ):
        print 'Usage: ' + str(sys.argv[0]) + ' ' + \
              '<maxlinks> <maxdegree> <topology> <targetprogram> [<args>]'
        print '<maxlinks> constrains the link count in the novel topology'
        print '           and must be >= 9'
        print '<maxdegree> constrains node degree in the novel topology'
        print '            and must be >= 4'
        print '<topology> can be "novel", "ring", "mesh", or "torus"'
        sys.exit(0)

def parse_sim_output(o):
    # parse stdout from simulation
    inst = 0
    stns = 0
    cyc = 0
    linespastx86 = 0
    for line in o.splitlines():
        if re.match(r'\[ x86 \]', line):
            linespastx86 = 0
        if ( re.match(r'CommittedInstructions = ', line) and
             linespastx86 == 7
           ):
            inst = float(re.sub(r'^CommittedInstructions = ([0-9]+).*$', \
                                r'\1', line))
        if re.match(r'SimTime = ', line) and linespastx86 == 12:
            # simulated time in nanoseconds
            stns = float(re.sub(r'^SimTime = ([0-9]+).*$', r'\1', line))
        if re.match(r'Cycles = ', line) and linespastx86 == 14:
            cyc = float(re.sub(r'^Cycles = ([0-9]+).*$', r'\1', line))
        linespastx86 += 1
    # simulated time in seconds (divide nanoseconds by 10^9)
    return inst, stns, cyc

def read_net_report(reportfile):
    # parse "net-report.txt" from simulation to get total NoC traffic
    totaltraffic = 0
    trans = 0
    avgms = 0
    avgly = 0
    linespastgeneral = 0
    linespastnodename = 0
    rpt = open(reportfile)
    for line in rpt:
        # find general stats section
        if re.match(r'\[ Network.net0.General\ ]', line):
            linespastgeneral = 0
        # record general stats
        if re.match(r'Transfers = ', line) and linespastgeneral == 1:
            trans = float(re.sub(r'^Transfers = ([0-9]+)', r'\1', line))
        if ( re.match(r'AverageMessageSize = ', line) and 
             linespastgeneral == 2
           ):
            avgms = float(re.sub(r'^AverageMessageSize = ([0-9]+)', \
                                 r'\1', line))
        if ( re.match(r'AverageLatency = ', line) and 
             linespastgeneral == 3
           ):
            avgly = float(re.sub(r'^AverageLatency = ([0-9]+)', \
                                 r'\1', line))
        # find report section names describing node statistics
        if re.match(r'\[ Network.net0.Node.n', line):
            linespastnodename = 0
        # the second line after such a node name gives the bytes sent
        if re.match(r'SentBytes = ', line) and linespastnodename == 2:
            totaltraffic += float(re.sub(r'^SentBytes = ([0-9]+)', r'\1', line))
        linespastgeneral += 1
        linespastnodename += 1
    rpt.close()
    return trans, avgms, avgly, totaltraffic

if __name__ == "__main__":
    # update path to simulator (or just 'm2s' if it's in $PATH)
    sim = '/home/csd305/Documents/Multicore/multi2sim-4.2/bin/m2s'

    # future work: accept these as command line args,
    # and update writeconfigs.py so it can create files
    # for mesh, torus, etc. for an arbitray number of cores
    cores = 9
    # threadspercore = 1 # assumed to be 1 for this version

    check_args(sys.argv)

    # create config files for profiling run of simulator
    exe = str(sys.argv[4])
    args = ''
    for a in sys.argv[5:]:
        args = args + str(a) + ' '
    args = args.strip()
    wc.write_ctx(exe, args)
    wc.write_cpu(cores)
    wc.write_mem(cores)
    wc.write_net_ring(cores)
    wc.write_net_mesh(cores)
    wc.write_net_torus(cores)
    
    # run simulator for novel and standard topologies
    topology =  str(sys.argv[3])
    cfg = topology + '-net-config.txt'
    rpt = topology + '-net-report.txt'
    o = subprocess.Popen([sim, '--x86-sim', 'detailed', \
                          '--x86-max-inst', '100000000', \
                          '--x86-config', 'cpu-config.txt', \
                          '--ctx-config', 'ctx-config.txt', \
                          '--mem-config', 'mem-config.txt', \
                          '--net-config', cfg, \
                          '--net-report', rpt], \
                          stderr=subprocess.STDOUT, \
                          stdout=subprocess.PIPE).communicate()[0]
    inst, simtimens, cycles = parse_sim_output(o)
    print 'Instructions:', inst
    print 'Nanoseconds:', simtimens
    print 'Cycles:', cycles
    transfers, avgmsgsize, avglatency, totaltraffic = read_net_report(rpt)
    print 'NoC Transfers (# Packets Sent):', transfers
    print 'NoC Avg. Message (Packet) Size:', avgmsgsize
    print 'NoC Average Latency (in Cycles):', avglatency
    print 'NoC Total Traffic (bytes):', totaltraffic
