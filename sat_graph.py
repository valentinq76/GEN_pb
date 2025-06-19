import subprocess
import re
import requests
import networkx as nx
from pathlib import Path
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class DerivationNode:
    """Nœud représentant une clause dans le graphe de dérivation E-prover."""
    
    clause_id: str
    clause_formula: str
    parents: List[str] = field(default_factory=list)
    inference: str = ""
    role: str = "plain"
    interesting_score: float = 0.0
    other_agint_metrics: Dict[str, float] = field(default_factory=dict)
    full_cnf_clause: str = ""

### fonction qui orchestre tout 

def generate_derivation_graph(axiom_file: str, save_output: bool = True,
                                output_dir: str = "eprover_output",ranking: bool = True):
    G = run_eprover_and_build_graph(axiom_file,save_output,output_dir)
    if ranking == True :
        G = enrich_graph_with_agint(G)
    return G

###create derivation graphe from e saturation

def run_eprover_and_build_graph(axiom_file: str, save_output: bool = True, 
                                output_dir: str = "eprover_output") -> nx.DiGraph:
    """
    Lance E-prover et construit le graphe de dérivation.
    """
    
    # 1. Lancer E-prover
    cmd = [
        'eprover',
        '--proof-graph=2',
        '--full-deriv',
        '--force-deriv=1',
        '--output-level=1',
        '--generated-limit=1000',
        axiom_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print("E-prover timeout")
        return nx.DiGraph()
    except Exception as e:
        print(f"Erreur E-prover: {e}")
        return nx.DiGraph()
    
    # 2. Sauvegarder si demandé
    if save_output:
        Path(output_dir).mkdir(exist_ok=True)
        base_name = Path(axiom_file).stem
        with open(f"{output_dir}/{base_name}_stdout.txt", 'w') as f:
            f.write(stdout)
        with open(f"{output_dir}/{base_name}_stderr.txt", 'w') as f:
            f.write(stderr)
    
    # 3. Parser et construire le graphe
    return _parse_digraph_to_networkx(stdout)


def _parse_digraph_to_networkx(eprover_output: str) -> nx.DiGraph:
    """Parse le digraph E-prover et retourne un graphe NetworkX."""
    
    # Extraire le digraph
    start = eprover_output.find("digraph proof{")
    if start == -1:
        return nx.DiGraph()
    
    end = eprover_output.rfind("}")
    digraph_content = eprover_output[start:end + 1]
    
    # Parser nœuds et arêtes
    nodes = _extract_nodes(digraph_content)
    edges = _extract_edges(digraph_content)
    
    # Construire le graphe NetworkX
    graph = nx.DiGraph()
    
    # Ajouter les nœuds
    for node_id, node_obj in nodes.items():
        graph.add_node(node_id, data=node_obj)
    # Ajouter les arêtes et mettre à jour les parents
    for parent, child in edges:
        if parent in nodes and child in nodes:
            graph.add_edge(parent, child)
            nodes[child].parents.append(parent)
    
    return graph


def _extract_nodes(digraph: str) -> Dict[str, 'DerivationNode']:
    """Extrait tous les nœuds du digraph."""
    
    nodes = {}
    
    # NOUVELLE REGEX FINALE :
    # Le ^ ancre la recherche au début de chaque ligne.
    node_pattern = r'^\s*(\d+)\s*\[[^\]]*?label="((?:.|\n)*?)"'
    
    # On utilise re.MULTILINE pour que le ^ fonctionne sur chaque ligne.
    # On n'a plus besoin de re.DOTALL grâce à la nouvelle capture du label.
    for match in re.finditer(node_pattern, digraph, re.MULTILINE):
        node_num = match.group(1)
        # Le contenu du label est maintenant dans le groupe 2
        label_content = match.group(2).replace('\\n', '\n')
        
        clause_id, role, formula, inference = _parse_node_label(label_content)
        
        if clause_id:
            # On garde la sécurité anti-surécriture
            if node_num not in nodes:
                node = DerivationNode(
                    clause_id=clause_id,
                    clause_formula=formula,
                    role=role,
                    inference=inference,
                    full_cnf_clause=f"cnf({clause_id},{role},{formula})"
                )
                nodes[node_num] = node
    return nodes


def _extract_edges(digraph: str) -> list:
    """Extrait toutes les arêtes du digraph."""
    
    edges = []
    edge_pattern = r'(\d+)\s*->\s*(\d+)'
    
    for match in re.finditer(edge_pattern, digraph):
        parent = match.group(1)
        child = match.group(2)
        edges.append((parent, child))
    
    return edges


def _parse_node_label(label: str) -> Tuple[str, str, str, str]:
    """
    Parse le label d'un nœud pour extraire clause_id, role, formula, inference.
    
    Exemple: 'cnf(c_0_8, plain, (formula),\ninference(...))'
    """
    
    # Nettoyer le label
    clean_label = label.strip()
    
    # Extraire la partie cnf(...)
    cnf_match = re.match(r'cnf\(([^,]+),\s*([^,]+),\s*(.+)', clean_label, re.DOTALL)
    if not cnf_match:
        return "", "", "", ""
    
    clause_id = cnf_match.group(1).strip()
    role = cnf_match.group(2).strip()
    rest = cnf_match.group(3).strip()
    
    # Séparer formule et inference
    # Chercher la première occurrence d'une nouvelle ligne suivie d'un mot-clé
    inference_start = re.search(r'\n(inference|file|[a-z_]+)', rest)
    
    if inference_start:
        formula = rest[:inference_start.start()].strip()
        inference = rest[inference_start.start():].strip()
    else:
        formula = rest
        inference = ""
    
    # Nettoyer seulement la virgule finale si présente
    if formula.endswith(','):
        formula = formula[:-1]
    
    formula = formula.strip()
    if inference.startswith('inference'):
        inference = inference[:-2]
    else :
        inference = inference.rstrip(').')
    return clause_id, role, formula, inference


###CALL AIGINT FOR RATING 



def enrich_graph_with_agint(graph: nx.DiGraph) -> nx.DiGraph:
    """
    Enrichit le graphe avec les scores AGInT de manière compacte.
    
    Args:
        graph: Graphe NetworkX avec nœuds DerivationNode
        
    Returns:
        Graphe enrichi avec scores AGInT
    """
    
    # 1. Extraire toutes les clauses CNF
    tptp_content = _extract_tptp_from_graph(graph)
    
    # 2. Appeler AGInT
    agint_output = _call_agint(tptp_content)
    if not agint_output:
        print("Échec AGInT")
        return graph
    # 3. Parser et mettre à jour les nœuds
    scores_map = _parse_agint_scores(agint_output)
    
    for node_id in graph.nodes():
        node = graph.nodes[node_id]['data']
        if node.clause_id in scores_map:
            score_data = scores_map[node.clause_id]
            node.interesting_score = score_data.get('interesting', 0.0)
            node.other_agint_metrics = {k: v for k, v in score_data.items() 
                                       if k != 'interesting'}
    
    print(f"AGInT: {len(scores_map)} nœuds enrichis")
    return graph


def _extract_tptp_from_graph(graph: nx.DiGraph) -> str:
    """Extrait toutes les clauses CNF du graphe au format AGInT."""
    
    clauses = []
    for node_id in graph.nodes():
        node = graph.nodes[node_id]['data']
        
        # Prendre la formule telle quelle
        formula = node.clause_formula
        
        # Source simple : clause_id si pas d'inference, sinon nettoyer l'inference
        if not node.inference or node.inference.startswith('file('):
            clause = f"cnf({node.clause_id},{node.role},{formula})."
            clauses.append(clause)
        else:
            source = node.inference
            clause = f"cnf({node.clause_id},{node.role},{formula},{source})."
            clauses.append(clause)
        
    return "\n".join(clauses)


def _call_agint(tptp_content: str) -> str:
    """Appelle AGInT et retourne la sortie."""
    
    payload = {
        "ProblemSource": "FORMULAE",
        "FORMULAEProblem": tptp_content,
        "SolutionFormat": "TPTP",
        "QuietFlag": "-q01",
        "SubmitButton": "ProcessSolution",
        "System___AGInTRater---0.0": "AGInTRater---0.0",
        "TimeLimit___AGInTRater---0.0": "60",
        "Transform___AGInTRater---0.0": "none",
        "Format___AGInTRater---0.0": "tptp:raw",
        "Command___AGInTRater---0.0": "AGInTRater -c %s"
    }
    
    try:
        response = requests.post(
            "https://tptp.org/cgi-bin/SystemOnTPTPFormReply",
            data=payload, timeout=70
        )
        response.raise_for_status()
        
        # Extraire contenu <PRE>
        text = response.text
        start = text.find("<PRE>") + 5
        end = text.find("</PRE>")
        return text[start:end] if start > 4 and end > 0 else ""
        
    except Exception as e:
        print(f"Erreur AGInT: {e}")
        return ""


def _parse_agint_scores(agint_output: str) -> dict:
    """Parse la sortie AGInT et retourne un dict {clause_id: {metric: score}}."""
    
    scores_map = {}
    
    # REGEX FINALE ET CORRIGÉE : Le ? dans (\[.*?\]) la rend non-gourmande.
    pattern = r'cnf\(([^,]+),.*?(\[.*?\])\s*\)\.'
    
    # On utilise re.DOTALL car les clauses cnf(...) s'étendent sur plusieurs lignes.
    for match in re.finditer(pattern, agint_output, re.DOTALL):
        clause_id = match.group(1).strip()
        scores_str = match.group(2) # Contient le bloc de scores, ex: "[interesting(1.00),...]"
        
        scores = {}
        for score_match in re.finditer(r'(\w+)\(([^)]+)\)', scores_str):
            metric = score_match.group(1).lower()
            value_str = score_match.group(2).strip()
            
            if value_str.lower() != "ignored":
                try:
                    scores[metric] = float(value_str)
                except ValueError:
                    pass
        
        if scores:
            scores_map[clause_id] = scores
            
    return scores_map