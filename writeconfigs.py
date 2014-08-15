"""This module writes the necessary Multi2Sim configuration files
(corresponding to the Multi2Sim options --ctx-config, --x86-config
--mem-config, and --net-config) into the current directory.
"""
import sys
import re
import networkx as nx

# context
def write_ctx(exe, args):
    f = open('ctx-config.txt', 'w')
    f.write('[Context 0]\n')
    f.write('Exe = ' + exe + '\n')
    f.write('Args = ' + args + '\n')
    f.close()

# cpu
def write_cpu(cores):
    f = open('cpu-config.txt', 'w')
    f.write('[ General ]\n')
    f.write('Cores = ' + str(cores) + '\n')
    f.write('Threads = 1\n')
    f.close()

# memory
def write_mem(cores):
    f = open('mem-config.txt', 'w')
    # cache geometries
    f.write('[CacheGeometry geo-l1]\nSets = 128\nAssoc = 2\n' + \
            'BlockSize = 256\nLatency = 2\nPolicy = LRU\nPorts = 2\n')
    f.write('\n[CacheGeometry geo-l2]\nSets = 512\nAssoc = 4\n' + \
            'BlockSize = 256\nLatency = 20\nPolicy = LRU\nPorts = 4\n')
    # L1 cache - one module per core
    for i in range(0, cores):
        si = str(i)
        f.write('\n[Module mod-l1-' + si + ']\n')
        f.write('Type = Cache\nGeometry = geo-l1\nLowNetwork = net0\n')
        f.write('LowNetworkNode = n' + si + '\n')
        f.write('LowModules = mod-l2-0 mod-l2-1\n')
    # L2 cache - two modules each handling half of address space
    # each L2 module gets its own node in the network with the cores
    f.write('\n[Module mod-l2-0]\nType = Cache\n' + \
            'Geometry = geo-l2\nHighNetwork = net0\n' + \
            'HighNetworkNode = n' + str(cores) + '\n' + \
            'LowNetwork = net-l2-mm\nLowModules = mod-mm\n' + \
            'AddressRange = BOUNDS 0x00000000 0x7FFFFFFF\n')
    f.write('\n[Module mod-l2-1]\nType = Cache\n' + \
            'Geometry = geo-l2\nHighNetwork = net0\n' + \
            'HighNetworkNode = n' + str(cores + 1) + '\n' + \
            'LowNetwork = net-l2-mm\nLowModules = mod-mm\n' + \
            'AddressRange = BOUNDS 0x80000000 0xFFFFFFFF\n')
    # main memory
    f.write('\n[Module mod-mm]\nType = MainMemory\nBlockSize = 256\n' + \
            'Latency = 100\nHighNetwork = net-l2-mm\n')
    # default L2-to-main memory network
    f.write('\n[Network net-l2-mm]\nDefaultInputBufferSize = 1024\n' + \
            'DefaultOutputBufferSize = 1024\nDefaultBandwidth = 256\n')
    # cores and their connections to L1
    for i in range(0, cores):
        si = str(i)
        f.write('\n[Entry core-' + si + ']\n')
        f.write('Arch = x86\nCore = ' + si + '\n')
        f.write('Thread = 0\nDataModule = mod-l1-' + si + '\n')
        f.write('InstModule = mod-l1-' + si + '\n')
    f.close()

# network: write portion of net-config that is common to all topologies
def write_net_common(cores, f):
    # default network characteristics
    f.write('[Network.net0]\nDefaultInputBufferSize = 1024\n' + \
            'DefaultOutputBufferSize = 1024\nDefaultBandwidth = 256\n')
    # create node, switch, and node-switch-link for each core
    for i in range(0, cores):
        si = str(i)
        f.write('\n[Network.net0.Node.n' + si + ']\nType = EndNode\n')
        f.write('\n[Network.net0.Node.sw' + si + ']\nType = Switch\n')
        f.write('\n[Network.net0.Link.sw' + si + '-n' + si + ']\n' + \
                'Source = sw' + si + '\nDest = n' + si + '\n' + \
                'Type = Bidirectional\n')
    # create nodes for each L2 module and links from those nodes
    # to the switches associated with the first three cores
    f.write('\n[Network.net0.Node.n' + str(cores + 0) + ']\n' + \
            'Type = EndNode\n')
    f.write('\n[Network.net0.Node.n' + str(cores + 1) + ']\n' + \
            'Type = EndNode\n')
    # L2-0 connects to sw0 & sw1; L2-1 connects to sw1 & sw2
    f.write('\n[Network.net0.Link.sw0-n' + str(cores + 0) + ']\n' + \
            'Source = sw0\nDest = n' + str(cores + 0) + '\n' + \
            'Type = Bidirectional\n')
    f.write('\n[Network.net0.Link.sw1-n' + str(cores + 0) + ']\n' + \
            'Source = sw1\nDest = n' + str(cores + 0) + '\n' + \
            'Type = Bidirectional\n')
    f.write('\n[Network.net0.Link.sw1-n' + str(cores + 1) + ']\n' + \
            'Source = sw1\nDest = n' + str(cores + 1) + '\n' + \
            'Type = Bidirectional\n')
    f.write('\n[Network.net0.Link.sw2-n' + str(cores + 1) + ']\n' + \
            'Source = sw2\nDest = n' + str(cores + 1) + '\n' + \
            'Type = Bidirectional\n')
    f.write('\n; above applies to all topologies\n')

# network: fully-connected
def write_net_fully(cores):
    f = open('fully-net-config.txt', 'w')
    write_net_common(cores, f)
    # links between switches
    f.write('; below describes a fully-connected NoC\n')
    for i in range(0, cores+1):
        si = str(i)
        for j in range(i+1, cores):
            sj = str(j)
            f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
                    'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
                    'Type = Bidirectional\n')
    f.close()

# network: novel network (use graph)
def write_net_novel(cores, graph):
    f = open('novel-net-config.txt', 'w')
    write_net_common(cores, f)
    f.write('; below describes a novel topology\n')
    for e in graph.edges_iter():
        si = str(e[0])
        sj = str(e[1])
        f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
                'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
                'Type = Bidirectional\n')
    f.close()

# network: ring
def write_net_ring(cores):
    f = open('ring-net-config.txt', 'w')
    write_net_common(cores, f)
    f.write('; below describes a ring topology\n')
    for i in range(0, cores-1):
        si = str(i)
        sj = str(i+1)
        f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
                'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
                'Type = Bidirectional\n')
    si = str(cores - 1)
    sj = str(0)
    f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
            'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
            'Type = Bidirectional\n')
    f.close()

# network: mesh
def write_net_mesh(cores):
    f = open('mesh-net-config.txt', 'w')
    write_net_common(cores, f)
    f.write('; below describes a mesh topology\n')
    # the below is hard-coded for 9 cores
    # future work: make this work for arbitrary # of cores
    el = [(0,1), (1,2), (0,3), (1,4), (2,5), (3,4), (4,5), (3,6), \
          (4,7), (5,8), (6,7), (7,8)]
    for e in el:
        si = str(e[0])
        sj = str(e[1])
        f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
                'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
                'Type = Bidirectional\n')
    f.close()

# network: torus
def write_net_torus(cores):
    f = open('torus-net-config.txt', 'w')
    write_net_common(cores, f)
    f.write('; below describes a torus topology\n')
    # the below is hard-coded for 9 cores
    # future work: make this work for arbitrary # of cores
    el = [(0,1), (1,2), (0,3), (1,4), (2,5), (3,4), (4,5), (3,6), \
          (4,7), (5,8), (6,7), (7,8), \
          (0,2), (3,5), (6,8), (0,6), (1,7), (2,8)]
    for e in el:
        si = str(e[0])
        sj = str(e[1])
        f.write('\n[Network.net0.Link.sw' + si + '-sw' + sj + ']\n' + \
                'Source = sw' + si + '\nDest = sw' + sj + '\n' + \
                'Type = Bidirectional\n')
    f.close()
