#!/usr/bin/env python
import sys
import subprocess
import re
import operator
import networkx as nx
import writeconfigs as wc

def check_args(argv = sys.argv):
    # check if target program provided on command line
    if ( len(sys.argv) < 4 or
         int(sys.argv[1]) < 9 or
         int(sys.argv[2]) < 4
    ):
        print 'Usage: ' + str(sys.argv[0]) + ' ' + \
              '<maxlinks> <maxdegree> <targetprogram> [<args>]'
        print '<maxlinks> constrains the link count in the novel topology'
        print '           and must be >= 9'
        print '<maxdegree> constrains node degree in the novel topology'
        print '            and must be >= 4'
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
    return inst, stns, cyc

def build_graph():
    # build graph from "net-report.txt" created in profiling step
    # edge weight represents bytes transferred across that link
    # each link listed twice in "net-report.txt" for traffic in each direction
    G=nx.Graph()
    linkname = re.compile(r'\[ Network\.net0\.Link\.link_' + \
                          r'<sw[0-9]+\.out_buf_[0-9]+>_' + \
                          r'<sw[0-9]+\.in_buf_[0-9]+> \]')
    node1 = -1
    node2 = -1
    trans = 0
    avgms = 0
    avgly = 0
    totaltraffic = 0
    linespastgeneral = 0
    linespastlinkname = 0
    linespastnodename = 0
    rpt = open('fully-net-report.txt')
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
        # find report section names describing switch-to-switch links
        if re.match(linkname, line):
            node1 = int(re.sub(r'^.*link_<sw([0-9]+)\.out.*$', r'\1', line))
            node2 = int(re.sub(r'^.*>_<sw([0-9]+)\.in.*$', r'\1', line))
            linespastlinkname = 0
        # the third line after such a link name gives the weight
        if re.match(r'TransferredBytes = ', line) and linespastlinkname == 3:
            wt = int(re.sub(r'^TransferredBytes = ([0-9]+)', r'\1', line))
            if G.has_edge(node1, node2):
                oldwt = G.edge[node1][node2]['weight']
                wt = wt + oldwt
                G.edge[node1][node2]['weight'] = wt
            else:
                G.add_edge(node1, node2, weight=wt)
        # find report section names describing node statistics
        if re.match(r'\[ Network.net0.Node.n', line):
            linespastnodename = 0
        # the second line after such a node name gives the bytes sent
        if re.match(r'SentBytes = ', line) and linespastnodename == 2:
            totaltraffic += float(re.sub(r'^SentBytes = ([0-9]+)', r'\1', line))
        linespastgeneral += 1
        linespastlinkname += 1
        linespastnodename += 1
    rpt.close()
    return G, trans, avgms, avgly, totaltraffic

def edges_sorted_by_weight(graph):
    # get a list of edges sorted by weight incr. ((n1, n2), w)
    el = []
    for e in graph.edges_iter():
        el.append( ( (e[0], e[1]), graph[e[0]][e[1]]['weight'] ) )
    el.sort(key=operator.itemgetter(1))
    return el

def replace_edge(graph, rel, maxl, maxd):
    if graph.number_of_edges() < maxl:
        # sort by weight descending (consider heaviest first)
        rel.sort(key=operator.itemgetter(1), reverse=True)
        i = 0
        while ( graph.number_of_edges() < maxlinks and
                i < maxl * 100
              ):
            re = rel.pop(0)
            rn1 = re[0][0]
            rn2 = re[0][1]
            rw = re[1]
            # replace edge if each node's degree allows
            if ( graph.degree(rn1) < maxd and
                 graph.degree(rn2) < maxd
               ):
                # add edge back in w/ weight zero
                # traffic may then be rerouted over the added link
                graph.add_edge(rn1, rn2, weight=0)
            else:
                # if node degrees won't allow this edge to be
                # replaced, put it back in the removed edge list
                rel.append( ((rn1, rn2), rw) )
            # make sure this while loop doesn't go forever
            i += 1

def reroute_traffic(graph, rn1, rn2, rw, rel, maxl, maxd): 
    # replace links, if needed, prior to rerouting traffic
    # link count may drop below maxlinks when working with maxdegree
    replace_edge(graph, rel, maxl, maxd)
    # record removed link info in rel
    rel.append( ((rn1, rn2), rw) )
    # find lowest weight path between the newly disconnected nodes
    sp = nx.shortest_path(graph, rn1, rn2, 'weight')
    # add weight (traffic) from removed link to links in new path
    for n in range(0, len(sp) - 1):
        graph[sp[n]][sp[n+1]]['weight'] += rw

def remove_edge_first_pass(graph, edge, rel, maxl, maxd):
    rn1 = edge[0][0]
    rn2 = edge[0][1]
    rw = edge[1]
    graph.remove_edge(rn1, rn2)
    if nx.is_connected(graph):
        reroute_traffic(graph, rn1, rn2, rw, rel, maxl, maxd)
    else:
        # if graph disconnected, restore edge
        graph.add_edge(rn1, rn2, weight=rw)

def reconnect_subgraphs(graph, subgraphs, rel, maxl, maxd):
    tel = []
    for gr in subgraphs:
        el = []
        el = edges_sorted_by_weight(gr)
        tel.append( ( (el[0][0][0], el[0][0][1]), el[0][1] ) )
    rn1_1 = tel[0][0][0]
    rn2_1 = tel[0][0][1]
    rw_1 = tel[0][1]
    rn1_2 = tel[1][0][0]
    rn2_2 = tel[1][0][1]
    rw_2 = tel[1][1]
    graph.remove_edge(rn1_1, rn2_1)
    graph.remove_edge(rn1_2, rn2_2)
    graph.add_edge(rn1_1, rn1_2, weight=0)
    graph.add_edge(rn2_1, rn2_2, weight=0)
    reroute_traffic(graph, rn1_1, rn2_1, rw_1, rel, maxl, maxd)
    reroute_traffic(graph, rn1_2, rn2_2, rw_2, rel, maxl, maxd)

def remove_edge_second_pass(graph, edge, rel, maxl, maxd):
    rn1 = edge[0][0]
    rn2 = edge[0][1]
    rw = edge[1]
    graph.remove_edge(rn1, rn2)
    if nx.is_connected(graph):
        reroute_traffic(graph, rn1, rn2, rw, rel, maxl, maxd)
    else:
        # if graph disconnected, remove anyway then reconnect
        sgl = nx.connected_component_subgraphs(graph)
        # but not if either subgraph has only one node
        if ( sgl[0].number_of_nodes == 1 or
             sgl[1].number_of_nodes == 1
           ):
            # can't fix subgraph w/ 1 node, so restore link
            graph.add_edge(rn1, rn2, weight=rw)
        else:
            reconnect_subgraphs(graph, sgl, rel, maxl, maxd)
            reroute_traffic(graph, rn1, rn2, rw, rel, maxl, maxd)

def cat_edges_by_neighbors(graph, node, maxd):
    hn = []
    ln = []
    he = []
    le = []
    for n in graph.neighbors_iter(node):
        d = graph.degree(n)
        # categorize neighbors as heavy or light
        if d > maxd:
            hn.append(n)
        else:
            ln.append(n)
    for n in hn:
        he.append( ( (node, n), graph[node][n]['weight'] ) )
    for n in ln:
        le.append( ( (node, n), graph[node][n]['weight'] ) )
    # sort lists of edges by weight
    he.sort(key=operator.itemgetter(1))
    le.sort(key=operator.itemgetter(1))
    return he, le

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
    exe = str(sys.argv[3])
    args = ''
    for a in sys.argv[4:]:
        args = args + str(a) + ' '
    args = args.strip()
    wc.write_ctx(exe, args)
    wc.write_cpu(cores)
    wc.write_mem(cores)
    wc.write_net_fully(cores)

    # run simulator with fully-connected NoC as profiling step
    o = subprocess.Popen([sim, '--x86-sim', 'detailed', \
                          '--x86-max-inst', '100000000', \
                          '--x86-config', 'cpu-config.txt', \
                          '--ctx-config', 'ctx-config.txt', \
                          '--mem-config', 'mem-config.txt', \
                          '--net-config', 'fully-net-config.txt', \
                          '--net-report', 'fully-net-report.txt'], \
                          stderr=subprocess.STDOUT, \
                          stdout=subprocess.PIPE).communicate()[0]

    inst, simtimens, cycles = parse_sim_output(o)
    print 'Instructions:', inst
    print 'Nanoseconds:', simtimens
    print 'Cycles:', cycles

    G, transfers, avgmsgsize, avglatency, totaltraffic = build_graph()
    print 'NoC Transfers (# Packets Sent):', transfers
    print 'NoC Avg. Message (Packet) Size:', avgmsgsize
    print 'NoC Average Latency (in Cycles):', avglatency
    print 'NoC Total Traffic (bytes):', totaltraffic

    # modify graph until constraints are met
    # (total link count and links per node)
    maxlinks = int(sys.argv[1])
    maxdegree = int(sys.argv[2])

    # preserve original graph
    # also don't use GN=G; that just creates a reference, not a copy
    GN = G.copy()

    # get a list of edges sorted by weight incr. ((n1, n2), w)
    el = edges_sorted_by_weight(GN)

    # iterate in incr. weight order; remove edge if maxlinks
    # constraint not satisfied and if graph will stay connected
    rel = []
    for e in el:
        if GN.number_of_edges() <= maxlinks:
            break
        remove_edge_first_pass(GN, e, rel, maxlinks, maxdegree)
    
    # get an updated  list of edges sorted by weight incr.
    el = edges_sorted_by_weight(GN)
    
    # if maxlinks constraint still not satisfied, then remove
    # links that will allow graph to disconnect, then reconnect it
    for e in el:
        if GN.number_of_edges() <= maxlinks:
            break
        remove_edge_second_pass(GN, e, rel, maxlinks, maxdegree)

    # now consider node degree constraint (maxdegree)
    # iterate thru nodes, remove edges as needed; start with
    # "heavy" edges connecting to other nodes exceeding maxdegree
    # replace removed edge w/ one from rel (removed edges list)
    for n in GN.nodes_iter():
        if GN.degree(n) > maxdegree:
            h = []
            l = []
            h, l = cat_edges_by_neighbors(GN, n, maxdegree)
            for e in h:
                if GN.degree(n) <= maxdegree:
                    break
                remove_edge_first_pass(GN, e, rel, maxlinks, maxdegree)
            for e in l:
                if GN.degree(n) <= maxdegree:
                    break
                remove_edge_first_pass(GN, e, rel, maxlinks, maxdegree) 
            # second pass, disconnect and reconnect graph if needed
            h = []
            l = []
            h, l = cat_edges_by_neighbors(GN, n, maxdegree)
            for e in h:
                if GN.degree(n) <= maxdegree:
                    break
                remove_edge_second_pass(GN, e, rel, maxlinks, maxdegree)
            for e in l:
                if GN.degree(n) <= maxdegree:
                    break
                remove_edge_second_pass(GN, e, rel, maxlinks, maxdegree)   
    
    wc.write_net_novel(cores, GN)
    print 'novel NoC topology written to "novel-net-config.txt" ' + \
          'for use by Multi2Sim' 
