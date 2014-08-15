NoC-topology
============

This repository contains a research project created for a school assignment. The project explores the optimal topology for interconnection circuitry between cores of a multicore, Network-on-a-Chip (Noc) processor.

This project was implemented as a tool written in Python. Please see ***Drews\_Final\_Report.pdf*** for a detailed report of the goals, methodology, and results of this project. I received a grade of "A" for this assignment.

###Project Contents

The tool consists of three Python files:

1. *tool.py*
  - this is step one of the tool which profiles the target app and creates the novel topology
  - usage: ./tool.py &lt;maxlinks&gt; &lt;maxdegree&gt; &lt;targetapp&gt;\[ &lt;targetappargs&gt;\]
  - usage: `./tool.py <maxlinks> <maxdegree> <targetapp>[ <targetappargs>]`
  - this outputs *novel-net-config.txt* desribing the new, novel topology
  - this also outputs the other config files needed by Multi2Sim
  - provides performance stats for the fully-connected topology to stdout

2. *comparisons.py*
  - this is step two which measures the performance of the target app with a specified topology
  - choices are "novel" (what was just generated by tool.py), "ring", "mesh", or "torus"
  - usage: ./comparisons.py &lt;maxlinks&gt; &lt;maxdegree&gt; &lt;topology&gt; &lt;target app&gt;\[ &lt;targetappargs&gt;\]
  - usage: `./comparisons.py <maxlinks> <maxdegree> <topology> <target app>[ <targetappargs>]`
  - this outputs the config files needed by Multi2Sim
  - provides performance stats for the specified topology to stdout

3. *writeconfigs.py*
  - imported by both tool.py and comparisons.py
  - not intended to be run directly; just a helper


###Necessary resources

1. Multi2Sim multicore hardware simulator
  - available from [www.multi2sim.org](https://www.multi2sim.org/)
  - need to update the path to m2s in the code of *tool.py* (at the top of the `__main__` section) to reflect the path on your machine
  - currently hardcoded to the absolute path to m2s in my filesystem

2. NetworkX
  - Python library created by people from LANL for graph manipulation
  - info at [networkx.github.io](http://networkx.github.io/)
  - Can be installed on RHEL using `easy_install --user networkx` or on Ubuntu using `apt-get install python-networkx` 

3. PARSEC multithreaded benchmark suite
  - I downloaded the pre-compiled versions from Multi2Sim; no need to compile them myself
  - [www.multi2sim.org/benchmarks/parsec-2.1.html](http://www.multi2sim.org/benchmarks/parsec-2.1.html)
  - see [parsec.cs.princeton.edu](http://parsec.cs.princeton.edu/) for more info
