"""Pixel graph with explicit intersection ambiguity and time-guided trails."""
import math
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize


def graph(mask):
    center = skeletonize(mask)
    pixels = set(map(tuple,np.argwhere(center)))
    adjacency = {}
    for p in sorted(pixels):
        y,x = p
        neighbors = []
        for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            q = y+dy,x+dx
            if q not in pixels:
                continue
            # Suppress redundant diagonal shortcuts at a right-angle corner.
            if dy and dx and ((y+dy,x) in pixels or (y,x+dx) in pixels):
                continue
            neighbors.append(q)
        adjacency[p] = neighbors
    junction = np.zeros_like(mask,bool)
    for p,neighbors in adjacency.items():
        if len(neighbors) > 2:
            junction[p] = True
    _, junctions = ndi.label(junction, structure=np.ones((3,3)))
    return center, adjacency, junctions


def trails(adjacency, birth, *, time_scale=0.1):
    """Contract junction blobs, pair ports, then cover every chain exactly once.

    Tiny skeleton junction edges are not independent gestures. Port pairing uses
    outward tangents plus arrival times; all such pairings remain uncertain in
    the trajectory contract. Coloured retracing is not observable from birth maps.
    """
    if not adjacency:
        return []
    shape = birth.shape
    junction = np.zeros(shape,bool)
    for p,neighbors in adjacency.items():
        if len(neighbors)>2:
            junction[p] = True
    regions,n = ndi.label(ndi.binary_dilation(junction,iterations=4),structure=np.ones((3,3)))
    nodes = {}
    members = {}
    for p in adjacency:
        if regions[p]:
            node = int(regions[p])
            nodes[p] = node
            members.setdefault(node,[]).append(p)
    for p,neighbors in adjacency.items():
        if p not in nodes and len(neighbors) != 2:
            n += 1
            nodes[p] = n
            members[n] = [p]
    # Components which are pure cycles need one explicit cut node.
    seen = set()
    for p in adjacency:
        if p in seen:
            continue
        stack,component = [p],[]
        while stack:
            q = stack.pop()
            if q in seen:
                continue
            seen.add(q)
            component.append(q)
            stack.extend(adjacency[q])
        if not any(q in nodes for q in component):
            q = min(component,key=lambda q:(birth[q],q))
            n += 1
            nodes[q] = n
            members[n] = [q]
    centers = {node:min(points,key=lambda p:sum(math.dist(p,q) for q in points)) for node,points in members.items()}
    def key(a,b):
        return (a,b) if a<b else (b,a)
    visited,edges,ports = set(),[],{}
    for p,node in sorted(nodes.items()):
        for q in adjacency[p]:
            if key(p,q) in visited or nodes.get(q) == node:
                continue
            chain = [p,q]
            visited.add(key(p,q))
            while chain[-1] not in nodes:
                choices = [r for r in adjacency[chain[-1]] if r != chain[-2]]
                if not choices:
                    break
                r = choices[0]
                visited.add(key(chain[-1],r))
                chain.append(r)
            other = nodes.get(chain[-1])
            if other is None:
                continue
            chain = [centers[node]]+chain+[centers[other]]
            index = len(edges)
            edges.append(chain)
            ports.setdefault(node,[]).append((index,0))
            ports.setdefault(other,[]).append((index,1))
    def outward(port):
        index,end = port
        chain = edges[index] if end==0 else edges[index][::-1]
        # Far enough from the crossing blob to estimate tangent and deposition.
        portion = chain[2:min(len(chain),14)] or chain
        target = portion[-1]
        origin = chain[0]
        vector = (target[0]-origin[0],target[1]-origin[1])
        norm = max(1e-9,math.hypot(*vector))
        times = [birth[p] for p in portion if birth[p]>=0]
        return np.array(vector)/norm, float(np.median(times)) if times else 0
    pairing = {}
    for node,items in ports.items():
        candidates = []
        for i,a in enumerate(items):
            va,ta = outward(a)
            for b in items[i+1:]:
                vb,tb = outward(b)
                # Geometry is dominant; observed time breaks competing tangents.
                cost = 4*(1+float(np.dot(va,vb)))+min(abs(ta-tb)/max(time_scale,0.001),10)*0.03
                candidates.append((cost,a,b))
        used = set()
        for cost,a,b in sorted(candidates):
            if a not in used and b not in used:
                pairing[a],pairing[b] = b,a
                used.update((a,b))
    paths = []
    remaining = set(range(len(edges)))
    def port_time(port):
        return outward(port)[1],port
    while remaining:
        options = [(i,end) for i in sorted(remaining) for end in (0,1)]
        unmatched = [p for p in options if p not in pairing]
        port = min(unmatched or options,key=port_time)
        path = []
        while port[0] in remaining:
            index,end = port
            remaining.remove(index)
            chain = edges[index] if end==0 else edges[index][::-1]
            path.extend(chain if not path else chain[1:])
            next_port = pairing.get((index,1-end))
            if next_port is None:
                break
            port = next_port
        if path and path[0] == path[-1]:
            # Rotate a closed gesture to the first observed deposition front.
            values = np.array([birth[p] for p in path[:-1]])
            local = ndi.median_filter(values,size=5,mode='wrap')
            first = int(np.argmin(local))
            path = path[first:-1]+path[:first]+[path[first]]
        paths.append(path)
    paths += [[p] for p in adjacency if not adjacency[p]]
    return paths


def isotonic(values):
    """Least-squares monotone arrival estimates (PAVA); keeps velocity samples."""
    groups = []
    for value in values:
        groups.append([float(value),1])
        while len(groups) > 1 and groups[-2][0] > groups[-1][0]:
            b, a = groups.pop(), groups.pop()
            n = a[1]+b[1]
            groups.append([(a[0]*a[1]+b[0]*b[1])/n,n])
    return [v for v,n in groups for _ in range(n)]
