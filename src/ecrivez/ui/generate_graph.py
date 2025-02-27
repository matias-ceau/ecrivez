from pathlib import Path

import yaml


def generate_html(content: str | Path) -> str:
    if isinstance(content, Path):
        with open(content, "r") as f:
            data = yaml.safe_load(f)
    else:
        data = yaml.safe_load(content)
    return f"""\
<!DOCTYPE html>
<html>
<head>
    <title>Graph Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        #mynetwork {{
            width: 800px;
            height: 600px;
            border: 1px solid lightgray;
        }}
    </style>
</head>
<body>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        // Create nodes and edges datasets
        var nodes = new vis.DataSet({str(data["nodes"])});
        var edges = new vis.DataSet({str(data["edges"])});

        // Create a network
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        var options = {{
            nodes: {{
                shape: 'circle',
                font: {{
                    size: 20
                }}
            }},
            edges: {{
                arrows: 'to'
            }},
            physics: {{
                enabled: true,
                solver: 'forceAtlas2Based'
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
