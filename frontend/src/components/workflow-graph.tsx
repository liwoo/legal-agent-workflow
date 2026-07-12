"use client";

import * as React from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type EdgeMarkerType,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { getWorkflowGraph } from "@/src/lib/api";
import { workflowNodeColors, workflowNodesLayout } from "@/src/data/workflow-graph";
import { cn } from "@/src/lib/utils";
import type { WorkflowEdge, WorkflowGraph as WorkflowGraphData, WorkflowNode, WorkflowNodeType } from "@/src/types";

interface WorkflowGraphProps {
  /** Nodes/edges to render. If omitted, the component fetches them itself. */
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  /** Node ids belonging to a specific contract's path through the graph — these get emphasized and everything else dims. */
  highlightedNodeIds?: string[];
  className?: string;
  heightClassName?: string;
}

const LEGEND: { type: WorkflowNodeType; label: string }[] = [
  { type: "node", label: "Node" },
  { type: "router", label: "Router" },
  { type: "validator", label: "Validator" },
  { type: "fan", label: "Fan-out" },
  { type: "reduce", label: "Reduce" },
  { type: "hitl", label: "Human-in-the-loop" },
  { type: "terminal", label: "Terminal" },
];

function GraphNode({ data }: NodeProps) {
  const nodeData = data as unknown as { label: string; nodeType: WorkflowNodeType; dimmed: boolean; emphasized: boolean };
  const colors = workflowNodeColors[nodeData.nodeType];

  return (
    <div
      className={cn(
        "rounded-lg border-2 px-3 py-2 text-center text-xs font-medium shadow-sm transition-opacity duration-200",
        nodeData.dimmed && "opacity-25",
        nodeData.emphasized && "ring-2 ring-offset-2 ring-offset-background"
      )}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
        color: colors.text,
        ...(nodeData.emphasized ? ({ ["--tw-ring-color" as string]: colors.border } as React.CSSProperties) : {}),
      }}
    >
      {nodeData.label}
    </div>
  );
}

const nodeTypes = { graphNode: GraphNode };

function buildFlowElements(
  data: WorkflowGraphData,
  highlightedNodeIds: string[] | undefined
): { nodes: Node[]; edges: Edge[] } {
  const layoutById = new Map(workflowNodesLayout.map((n) => [n.id, n]));
  const highlighted = new Set(highlightedNodeIds ?? []);
  const hasHighlight = highlighted.size > 0;

  // Build a set of highlighted edges: an edge is "on the path" if both its
  // endpoints are in the highlighted node set AND they're adjacent in the
  // path order (so we don't light up unrelated shortcuts between two
  // visited nodes).
  const pathOrder = highlightedNodeIds ?? [];
  const highlightedEdgeKeys = new Set<string>();
  for (let i = 0; i < pathOrder.length - 1; i += 1) {
    highlightedEdgeKeys.add(`${pathOrder[i]}->${pathOrder[i + 1]}`);
  }

  const nodes: Node[] = data.nodes.map((n) => {
    const layout = layoutById.get(n.id);
    const emphasized = hasHighlight && highlighted.has(n.id);
    const dimmed = hasHighlight && !highlighted.has(n.id);
    return {
      id: n.id,
      type: "graphNode",
      position: { x: layout?.x ?? 0, y: layout?.y ?? 0 },
      data: { label: n.label, nodeType: n.type, dimmed, emphasized },
      draggable: false,
    };
  });

  const edges: Edge[] = data.edges.map((e, idx) => {
    const key = `${e.source}->${e.target}`;
    const onPath = highlightedEdgeKeys.has(key);
    const dimmed = hasHighlight && !onPath;
    const marker: EdgeMarkerType = { type: "arrowclosed", width: 16, height: 16 };
    return {
      id: `${e.source}-${e.target}-${idx}`,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: onPath,
      style: {
        strokeDasharray: e.kind === "dashed" ? "5 4" : undefined,
        opacity: dimmed ? 0.2 : 1,
        strokeWidth: onPath ? 2.5 : 1.5,
        stroke: onPath ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
      },
      labelStyle: { fontSize: 10, fill: "hsl(var(--muted-foreground))" },
      markerEnd: marker,
    };
  });

  return { nodes, edges };
}

function WorkflowGraphInner({ nodes: nodesProp, edges: edgesProp, highlightedNodeIds, className, heightClassName }: WorkflowGraphProps) {
  const [fetched, setFetched] = React.useState<WorkflowGraphData | null>(null);
  const [loading, setLoading] = React.useState(nodesProp === undefined);

  React.useEffect(() => {
    if (nodesProp !== undefined && edgesProp !== undefined) return;
    let cancelled = false;
    setLoading(true);
    void getWorkflowGraph().then((data) => {
      if (!cancelled) {
        setFetched(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [nodesProp, edgesProp]);

  const data: WorkflowGraphData | null =
    nodesProp !== undefined && edgesProp !== undefined ? { nodes: nodesProp, edges: edgesProp } : fetched;

  const { nodes, edges } = React.useMemo(
    () => (data ? buildFlowElements(data, highlightedNodeIds) : { nodes: [], edges: [] }),
    [data, highlightedNodeIds]
  );

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className={cn("relative w-full overflow-hidden rounded-lg border border-border bg-muted/20", heightClassName ?? "h-[520px]")}>
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Loading workflow graph…
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            proOptions={{ hideAttribution: true }}
            nodesConnectable={false}
            nodesDraggable={false}
            elementsSelectable={false}
            zoomOnScroll
            panOnScroll
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="opacity-40" />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              className="!bg-background"
              nodeColor={(n) => {
                const t = (n.data as { nodeType?: WorkflowNodeType })?.nodeType;
                return t ? workflowNodeColors[t].border : "#94a3b8";
              }}
            />
          </ReactFlow>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        {LEGEND.map((item) => (
          <div key={item.type} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-sm border"
              style={{
                backgroundColor: workflowNodeColors[item.type].bg,
                borderColor: workflowNodeColors[item.type].border,
              }}
            />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Renders the contract-review agent graph via @xyflow/react. Fetches
 * nodes/edges from GET /api/workflow/graph by default (falling back to the
 * local fixture offline), or accepts them as props to avoid a refetch.
 * When `highlightedNodeIds` is supplied, the matching path is emphasized
 * and the rest of the graph dims.
 */
export function WorkflowGraph(props: WorkflowGraphProps) {
  return (
    <ReactFlowProvider>
      <WorkflowGraphInner {...props} />
    </ReactFlowProvider>
  );
}
