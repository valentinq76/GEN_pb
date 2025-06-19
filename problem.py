import networkx as nx

def extract_proof(G: nx.DiGraph, node_id_str: str) -> nx.DiGraph:
    """
    Extracts a proof graph from a given graph G starting from a specific node.

    Args:
        G: The original directed graph.
        node_id_str: The ID of the starting node as a string.

    Returns:
        A DiGraph representing the proof, containing all ancestors of the starting node.
    """
    proof_graph = nx.DiGraph()
    nodes_to_visit = {node_id_str}
    processed_nodes = set()

    while nodes_to_visit:
        current_node_id = nodes_to_visit.pop()

        if current_node_id in processed_nodes or current_node_id not in G:
            continue

        processed_nodes.add(current_node_id)

        # Ensure node_data is handled safely, defaulting to None if not found
        node_data = G.nodes[current_node_id].get('data')

        proof_graph.add_node(current_node_id, data=node_data)

        if node_data and hasattr(node_data, 'parents') and isinstance(node_data.parents, list):
            for parent_id in node_data.parents:
                nodes_to_visit.add(str(parent_id)) # Ensure parent_id is string
                if parent_id in G:
                    # Ensure parent node is in proof_graph before adding edge
                    if parent_id not in proof_graph:
                        parent_node_data = G.nodes[parent_id].get('data')
                        proof_graph.add_node(parent_id, data=parent_node_data)
                    proof_graph.add_edge(parent_id, current_node_id)
                elif str(parent_id) in G: # Check if parent_id (as string) is in G
                    parent_id_str = str(parent_id)
                    # Ensure parent node is in proof_graph before adding edge
                    if parent_id_str not in proof_graph:
                        parent_node_data = G.nodes[parent_id_str].get('data')
                        proof_graph.add_node(parent_id_str, data=parent_node_data)
                    proof_graph.add_edge(parent_id_str, current_node_id)


    return proof_graph
