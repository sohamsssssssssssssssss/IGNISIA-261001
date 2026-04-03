import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

export const PromoterGraph = ({ data }: { data: any }) => {
    const svgRef = useRef<SVGSVGElement>(null);

    useEffect(() => {
        if (!data || !svgRef.current) return;

        const width = 400;
        const height = 300;

        // Clear previous render
        d3.select(svgRef.current).selectAll("*").remove();

        const svg = d3.select(svgRef.current)
            .attr("viewBox", [0, 0, width, height]);

        // Deep copy nodes/links because D3 modifies them
        const nodes = data.nodes.map((d: any) => ({ ...d }));
        const links = data.links.map((d: any) => ({ ...d }));

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id((d: any) => d.id).distance(60))
            .force("charge", d3.forceManyBody().strength(-150))
            .force("center", d3.forceCenter(width / 2, height / 2));

        const link = svg.append("g")
            .attr("stroke", "rgba(255,255,255,0.2)")
            .attr("stroke-opacity", 0.6)
            .selectAll("line")
            .data(links)
            .join("line")
            .attr("stroke-width", 1.5);

        const nodeGroup = svg.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .call(d3.drag<any, any>()
                .on("start", (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on("drag", (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on("end", (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }));

        nodeGroup.append("circle")
            .attr("r", (d: any) => d.type === 'director' ? 8 : 12)
            .attr("fill", (d: any) => {
                if (d.status === 'clean') return "var(--success)";
                if (d.status === 'flagged') return "var(--warning)";
                if (d.status === 'defaulter') return "var(--danger)";
                return "var(--accent)";
            })
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5);

        nodeGroup.append("text")
            .text((d: any) => d.label)
            .attr("x", 15)
            .attr("y", 4)
            .style("font-size", "10px")
            .style("fill", "var(--text-secondary)")
            .style("pointer-events", "none"); // Prevent text blocking drag

        simulation.on("tick", () => {
            link
                .attr("x1", (d: any) => d.source.x)
                .attr("y1", (d: any) => d.source.y)
                .attr("x2", (d: any) => d.target.x)
                .attr("y2", (d: any) => d.target.y);

            nodeGroup
                .attr("transform", (d: any) => `translate(${d.x},${d.y})`);
        });

        return () => {
            simulation.stop();
        };

    }, [data]);

    return (
        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '10px' }}>
            <svg ref={svgRef} style={{ width: '100%', height: '300px' }}></svg>
        </div>
    );
};
