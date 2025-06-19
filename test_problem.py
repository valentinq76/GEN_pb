import unittest
import networkx as nx
from problem import extract_proof
from sat_graph import DerivationNode # Assuming DerivationNode is in sat_graph.py

class TestExtractProof(unittest.TestCase):

    def test_extract_proof_axiom_node(self):
        G = nx.DiGraph()
        axiom_data = DerivationNode(clause_id='a', clause_formula='a()', parents=[])
        G.add_node('A', data=axiom_data)

        proof_graph = extract_proof(G, 'A')
        self.assertEqual(proof_graph.number_of_nodes(), 1)
        self.assertIn('A', proof_graph.nodes)
        self.assertEqual(proof_graph.number_of_edges(), 0)

    def test_extract_proof_simple_chain(self):
        G = nx.DiGraph()
        node_a_data = DerivationNode(clause_id='a', clause_formula='a()', parents=[])
        node_b_data = DerivationNode(clause_id='b', clause_formula='b()', parents=['A'])
        node_c_data = DerivationNode(clause_id='c', clause_formula='c()', parents=['B'])

        G.add_node('A', data=node_a_data)
        G.add_node('B', data=node_b_data)
        G.add_node('C', data=node_c_data)
        # Edges in G are not strictly needed for extract_proof as it relies on parents attribute
        # but adding them for completeness of G's representation if it were used elsewhere.
        G.add_edge('A', 'B')
        G.add_edge('B', 'C')


        proof_graph = extract_proof(G, 'C')
        self.assertEqual(proof_graph.number_of_nodes(), 3)
        self.assertIn('A', proof_graph.nodes)
        self.assertIn('B', proof_graph.nodes)
        self.assertIn('C', proof_graph.nodes)

        self.assertEqual(proof_graph.number_of_edges(), 2)
        self.assertTrue(proof_graph.has_edge('B', 'C'))
        self.assertTrue(proof_graph.has_edge('A', 'B'))

        self.assertEqual(proof_graph.nodes['A']['data'].clause_id, 'a')
        self.assertEqual(proof_graph.nodes['B']['data'].clause_id, 'b')
        self.assertEqual(proof_graph.nodes['C']['data'].clause_id, 'c')

    def test_extract_proof_multiple_parents(self):
        G = nx.DiGraph()
        node_a_data = DerivationNode(clause_id='a', clause_formula='a()', parents=[])
        node_b_data = DerivationNode(clause_id='b', clause_formula='b()', parents=['A'])
        node_c_data = DerivationNode(clause_id='c', clause_formula='c()', parents=['A'])
        node_d_data = DerivationNode(clause_id='d', clause_formula='d()', parents=['B', 'C'])

        G.add_node('A', data=node_a_data)
        G.add_node('B', data=node_b_data)
        G.add_node('C', data=node_c_data)
        G.add_node('D', data=node_d_data)
        # G.add_edge('A', 'B') # Not strictly needed by extract_proof logic
        # G.add_edge('A', 'C') # Not strictly needed by extract_proof logic
        # G.add_edge('B', 'D') # Not strictly needed by extract_proof logic
        # G.add_edge('C', 'D') # Not strictly needed by extract_proof logic


        proof_graph = extract_proof(G, 'D')
        self.assertEqual(proof_graph.number_of_nodes(), 4)
        self.assertIn('A', proof_graph.nodes)
        self.assertIn('B', proof_graph.nodes)
        self.assertIn('C', proof_graph.nodes)
        self.assertIn('D', proof_graph.nodes)

        # Edges in proof_graph should be: (B,D), (C,D), (A,B), (A,C)
        self.assertEqual(proof_graph.number_of_edges(), 4) # Corrected expected number of edges
        self.assertTrue(proof_graph.has_edge('B', 'D'))
        self.assertTrue(proof_graph.has_edge('C', 'D'))
        self.assertTrue(proof_graph.has_edge('A', 'B'))
        self.assertTrue(proof_graph.has_edge('A', 'C'))

        self.assertEqual(proof_graph.nodes['D']['data'].clause_id, 'd')
        self.assertEqual(proof_graph.nodes['B']['data'].clause_id, 'b')
        self.assertEqual(proof_graph.nodes['C']['data'].clause_id, 'c')
        self.assertEqual(proof_graph.nodes['A']['data'].clause_id, 'a')


    def test_extract_proof_node_not_in_graph(self):
        G_empty = nx.DiGraph()
        proof_graph_empty = extract_proof(G_empty, 'A')
        self.assertEqual(proof_graph_empty.number_of_nodes(), 0)
        self.assertEqual(proof_graph_empty.number_of_edges(), 0)

        G_one_node = nx.DiGraph()
        G_one_node.add_node('B', data=DerivationNode(clause_id='b', clause_formula='b()', parents=[]))
        proof_graph_other_node = extract_proof(G_one_node, 'A') # 'A' is not in G_one_node
        self.assertEqual(proof_graph_other_node.number_of_nodes(), 0)
        self.assertEqual(proof_graph_other_node.number_of_edges(), 0)

    def test_extract_proof_graph_with_cycle_should_terminate(self):
        G = nx.DiGraph()
        # Cycle: A's parent is C, C's parent is B, B's parent is A
        node_a_data = DerivationNode(clause_id='a', clause_formula='a()', parents=['C'])
        node_b_data = DerivationNode(clause_id='b', clause_formula='b()', parents=['A'])
        node_c_data = DerivationNode(clause_id='c', clause_formula='c()', parents=['B'])

        G.add_node('A', data=node_a_data)
        G.add_node('B', data=node_b_data)
        G.add_node('C', data=node_c_data)
        # G.add_edge('C', 'A') # Not strictly needed
        # G.add_edge('A', 'B') # Not strictly needed
        # G.add_edge('B', 'C') # Not strictly needed

        proof_graph = extract_proof(G, 'A')

        # The function should terminate.
        # The proof graph should contain all nodes involved in the cycle leading to 'A'.
        # Since we start at 'A', its parent 'C' is added.
        # 'C's parent 'B' is added.
        # 'B's parent 'A' is already processed.
        self.assertEqual(proof_graph.number_of_nodes(), 3)
        self.assertIn('A', proof_graph.nodes)
        self.assertIn('B', proof_graph.nodes)
        self.assertIn('C', proof_graph.nodes)

        # Edges in proof graph: (C,A), (B,C), (A,B)
        self.assertEqual(proof_graph.number_of_edges(), 3)
        self.assertTrue(proof_graph.has_edge('C', 'A'))
        self.assertTrue(proof_graph.has_edge('B', 'C'))
        self.assertTrue(proof_graph.has_edge('A', 'B'))

        self.assertEqual(proof_graph.nodes['A']['data'].clause_id, 'a')
        self.assertEqual(proof_graph.nodes['B']['data'].clause_id, 'b')
        self.assertEqual(proof_graph.nodes['C']['data'].clause_id, 'c')

if __name__ == '__main__':
    unittest.main()
