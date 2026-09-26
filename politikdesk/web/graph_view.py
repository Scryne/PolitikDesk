"""Etkileşimli Siyasi İlişki ve İstihbarat Grafiği (Roadmap Faz 4.2 / Görselleştirme).

Aktörler, olaylar, vaatler, göstergeler ve çelişkiler arasındaki deterministik
ilişkileri (`event_relations`, `stance_shifts`, `entities`) görselleştirir.

⛔ MİMARİ KURAL: Graf verisi deterministiktir. LLM çağırmaz.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from politikdesk.db import connection
from politikdesk.observability import get_logger
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    card,
    icon,
    kpi,
    page,
    page_head,
)
from politikdesk.web.ui import format as fmt
from politikdesk.web.ui.tokens import DARK

log = get_logger(__name__)

router = APIRouter(tags=["web"])


def get_graph_data(
    *,
    limit_nodes: int = 45,
    relation_type: str | None = None,
) -> dict[str, Any]:
    """Deterministik olay ve siyasi ilişki grafı verilerini derler."""
    nodes_dict: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []

    color_actor = DARK["color-chart-1"]
    color_earlier = DARK["color-chart-2"]
    color_later = DARK["color-chart-3"]
    color_event = DARK["color-accent"]
    color_contra = DARK["color-contra"]
    color_strong = DARK["color-strong"]
    color_muted = DARK["color-fg-muted"]

    shifts = []
    relations = []
    try:
        with connection() as conn, conn.cursor() as cur:
            # 1. Stance Shifts (Söylem Değişiklikleri & Zıtlıklar)
            cur.execute(
                """
                SELECT s.id, s.actor_name, s.shift_type, s.topic_or_metric,
                       s.earlier_event_id, s.earlier_event_title,
                       s.later_event_id, s.later_event_title,
                       s.time_span_days, s.confidence, s.status
                  FROM stance_shifts s
                 WHERE s.status = 'open'
                 ORDER BY s.id DESC
                 LIMIT %s
                """,
                (limit_nodes,),
            )
            shifts = [dict(r) for r in cur.fetchall()]

            # 2. Event Relations (Updates, Contradicts, Same Thread)
            rel_filter = ""
            params: list[Any] = [limit_nodes]
            if relation_type:
                rel_filter = "WHERE er.relation = %s"
                params = [relation_type, limit_nodes]

            cur.execute(
                f"""
                SELECT er.from_event_id, er.to_event_id, er.relation,
                       er.similarity, e1.title AS from_title, e2.title AS to_title
                  FROM event_relations er
                  JOIN events e1 ON e1.id = er.from_event_id
                  JOIN events e2 ON e2.id = er.to_event_id
                 {rel_filter}
                 ORDER BY er.from_event_id DESC
                 LIMIT %s
                """,
                params,
            )
            relations = [dict(r) for r in cur.fetchall()]

        for s in shifts:
            actor_name = s["actor_name"]
            actor_node_id = f"actor:{actor_name}"
            if actor_node_id not in nodes_dict:
                nodes_dict[actor_node_id] = {
                    "id": actor_node_id,
                    "label": actor_name,
                    "type": "actor",
                    "group": "Siyasi Aktör",
                    "color": color_actor,
                    "size": 16,
                    "href": f"/memory?q={actor_name}",
                }

            e1_id = f"event:{s['earlier_event_id']}"
            e2_id = f"event:{s['later_event_id']}"

            if e1_id not in nodes_dict:
                nodes_dict[e1_id] = {
                    "id": e1_id,
                    "event_id": s["earlier_event_id"],
                    "label": s["earlier_event_title"][:40] + ("…" if len(s["earlier_event_title"]) > 40 else ""),
                    "full_title": s["earlier_event_title"],
                    "type": "event",
                    "group": "Geçmiş Beyan/Olay",
                    "color": color_earlier,
                    "size": 12,
                    "href": f"/event/{s['earlier_event_id']}",
                }

            if e2_id not in nodes_dict:
                nodes_dict[e2_id] = {
                    "id": e2_id,
                    "event_id": s["later_event_id"],
                    "label": s["later_event_title"][:40] + ("…" if len(s["later_event_title"]) > 40 else ""),
                    "full_title": s["later_event_title"],
                    "type": "event",
                    "group": "Güncel İcraat/Beyan",
                    "color": color_later,
                    "size": 12,
                    "href": f"/event/{s['later_event_id']}",
                }

            # Aktör -> Olay bağları
            links.append({
                "source": actor_node_id,
                "target": e1_id,
                "relation": "stated",
                "label": "Geçmiş Beyan",
                "color": color_muted,
                "dashed": True,
            })
            links.append({
                "source": actor_node_id,
                "target": e2_id,
                "relation": "stated",
                "label": "Son Beyan",
                "color": color_muted,
                "dashed": True,
            })

            # Olay1 <-> Olay2 Zıtlık Bağı
            shift_label = "U-Dönüşü" if s["shift_type"] == "reversal" else "Tutulmayan Vaat"
            links.append({
                "source": e1_id,
                "target": e2_id,
                "relation": s["shift_type"],
                "label": f"{shift_label} ({s['time_span_days']} gün)",
                "color": color_contra,
                "dashed": False,
                "confidence": float(s["confidence"] or 0.85),
            })

        for r in relations:
            e_from = f"event:{r['from_event_id']}"
            e_to = f"event:{r['to_event_id']}"

            if e_from not in nodes_dict:
                nodes_dict[e_from] = {
                    "id": e_from,
                    "event_id": r["from_event_id"],
                    "label": r["from_title"][:38] + ("…" if len(r["from_title"]) > 38 else ""),
                    "full_title": r["from_title"],
                    "type": "event",
                    "group": "Gelişme",
                    "color": color_event,
                    "size": 11,
                    "href": f"/event/{r['from_event_id']}",
                }

            if e_to not in nodes_dict:
                nodes_dict[e_to] = {
                    "id": e_to,
                    "event_id": r["to_event_id"],
                    "label": r["to_title"][:38] + ("…" if len(r["to_title"]) > 38 else ""),
                    "full_title": r["to_title"],
                    "type": "event",
                    "group": "Gelişme",
                    "color": color_event,
                    "size": 11,
                    "href": f"/event/{r['to_event_id']}",
                }

            rel_color = color_event
            if r["relation"] in ("contradicts", "fails"):
                rel_color = color_contra
            elif r["relation"] in ("fulfils", "supports"):
                rel_color = color_strong

            links.append({
                "source": e_from,
                "target": e_to,
                "relation": r["relation"],
                "label": r["relation"],
                "color": rel_color,
                "dashed": False,
                "confidence": float(r["similarity"] or 0.75),
            })
    except Exception as exc:
        log.warning("graph_data_db_failed", error=str(exc))

    nodes_list = list(nodes_dict.values())
    return {
        "nodes": nodes_list,
        "links": links,
        "stats": {
            "node_count": len(nodes_list),
            "link_count": len(links),
            "shift_count": len(shifts),
        },
    }


@router.get("/api/graph/data")
def graph_data_endpoint(
    limit: int = Query(45, ge=10, le=150),
    relation: str | None = None,
) -> dict[str, Any]:
    """Etkileşimli ağ grafiği için düğüm ve kenar JSON verisi."""
    return get_graph_data(limit_nodes=limit, relation_type=relation)


_GRAPH_JS = """
(function(){
  var graphData = null;
  var canvas = document.getElementById('pd-graph-canvas');
  var ctx = canvas ? canvas.getContext('2d') : null;
  var width = 960;
  var height = 580;
  var scale = 1.0;
  var panX = 0;
  var panY = 0;
  var isDragging = false;
  var startX, startY;
  var selectedNode = null;
  var simNodes = [];
  var simLinks = [];

  function initSimulation(data) {
    graphData = data;
    var nodeMap = {};
    simNodes = data.nodes.map(function(n, i){
      var angle = (i / data.nodes.length) * 2 * Math.PI;
      var radius = 180 + (i % 3) * 60;
      var node = {
        id: n.id,
        label: n.label,
        full_title: n.full_title || n.label,
        type: n.type,
        group: n.group,
        color: n.color,
        size: n.size || 12,
        href: n.href,
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
        vx: 0,
        vy: 0
      };
      nodeMap[n.id] = node;
      return node;
    });

    simLinks = data.links.map(function(l){
      return {
        source: nodeMap[l.source] || l.source,
        target: nodeMap[l.target] || l.target,
        relation: l.relation,
        label: l.label,
        color: l.color || 'var(--color-border-strong)',
        dashed: !!l.dashed
      };
    }).filter(function(l){
      return l.source && l.target && typeof l.source === 'object' && typeof l.target === 'object';
    });

    for (var iter = 0; iter < 50; iter++) {
      stepPhysics();
    }
    render();
  }

  function stepPhysics() {
    var k = 0.05;
    var repulse = 3500;
    for (var i = 0; i < simNodes.length; i++) {
      for (var j = i + 1; j < simNodes.length; j++) {
        var dx = simNodes[j].x - simNodes[i].x;
        var dy = simNodes[j].y - simNodes[i].y;
        var dist = Math.sqrt(dx*dx + dy*dy) || 1;
        if (dist < 300) {
          var f = repulse / (dist * dist);
          var fx = (dx / dist) * f;
          var fy = (dy / dist) * f;
          simNodes[i].x -= fx;
          simNodes[i].y -= fy;
          simNodes[j].x += fx;
          simNodes[j].y += fy;
        }
      }
    }
    for (var l = 0; l < simLinks.length; l++) {
      var s = simLinks[l].source;
      var t = simLinks[l].target;
      var ldx = t.x - s.x;
      var ldy = t.y - s.y;
      var ldist = Math.sqrt(ldx*ldx + ldy*ldy) || 1;
      var spring = (ldist - 120) * k;
      var sfx = (ldx / ldist) * spring;
      var sfy = (ldy / ldist) * spring;
      s.x += sfx;
      s.y += sfy;
      t.x -= sfx;
      t.y -= sfy;
    }
    for (var m = 0; m < simNodes.length; m++) {
      simNodes[m].x += (width/2 - simNodes[m].x) * 0.015;
      simNodes[m].y += (height/2 - simNodes[m].y) * 0.015;
    }
  }

  function render() {
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.translate(panX, panY);
    ctx.scale(scale, scale);

    // 1. Kenarlar (Links)
    for (var i = 0; i < simLinks.length; i++) {
      var link = simLinks[i];
      ctx.beginPath();
      ctx.strokeStyle = link.color;
      ctx.lineWidth = (link.relation === 'reversal' || link.relation === 'contradicts') ? 2 : 1.2;
      if (link.dashed) {
        ctx.setLineDash([4, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.moveTo(link.source.x, link.source.y);
      ctx.lineTo(link.target.x, link.target.y);
      ctx.stroke();

      if (link.label && scale > 0.75) {
        var mx = (link.source.x + link.target.x) / 2;
        var my = (link.source.y + link.target.y) / 2;
        ctx.font = '10px system-ui, sans-serif';
        ctx.fillStyle = link.color;
        ctx.fillText(link.label, mx + 4, my - 4);
      }
    }

    // 2. Düğümler (Nodes)
    for (var j = 0; j < simNodes.length; j++) {
      var n = simNodes[j];
      var isSel = selectedNode && selectedNode.id === n.id;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.size + (isSel ? 4 : 0), 0, 2 * Math.PI);
      ctx.fillStyle = n.color;
      ctx.fill();
      ctx.lineWidth = isSel ? 3 : 1.5;
      ctx.strokeStyle = isSel ? 'var(--color-fg)' : 'var(--color-bg)';
      ctx.stroke();

      ctx.font = (n.type === 'actor' ? 'bold 12px' : '11px') + ' system-ui, sans-serif';
      ctx.fillStyle = 'var(--color-fg)';
      ctx.fillText(n.label, n.x + n.size + 4, n.y + 4);
    }
    ctx.restore();
  }

  if (canvas) {
    canvas.addEventListener('mousedown', function(e){
      isDragging = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
    });

    window.addEventListener('mousemove', function(e){
      if (!isDragging) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      render();
    });

    window.addEventListener('mouseup', function(){
      isDragging = false;
    });

    canvas.addEventListener('wheel', function(e){
      e.preventDefault();
      var zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      scale = Math.max(0.4, Math.min(3.0, scale * zoomFactor));
      render();
    });

    canvas.addEventListener('click', function(e){
      var rect = canvas.getBoundingClientRect();
      var cx = (e.clientX - rect.left - panX) / scale;
      var cy = (e.clientY - rect.top - panY) / scale;

      var clicked = null;
      for (var i = 0; i < simNodes.length; i++) {
        var n = simNodes[i];
        var dist = Math.sqrt((cx - n.x)*(cx - n.x) + (cy - n.y)*(cy - n.y));
        if (dist <= n.size + 6) {
          clicked = n;
          break;
        }
      }
      selectedNode = clicked;
      updateInspector(clicked);
      render();
    });
  }

  function updateInspector(node) {
    var drawer = document.getElementById('node-inspector');
    if (!drawer) return;
    if (!node) {
      drawer.innerHTML = '<p class="subtle" style="margin:0">İncelemek istediğiniz düğüme tıklayın.</p>';
      return;
    }
    var html = '<div style="margin-bottom:var(--space-2)">' +
      '<span class="badge">' + (node.group || node.type) + '</span></div>' +
      '<h3 style="margin:0 0 var(--space-2);font-size:var(--text-md)">' + node.full_title + '</h3>' +
      '<p class="subtle" style="margin:0 0 var(--space-4);font-size:var(--text-xs)">Kimlik: ' + node.id + '</p>';
    if (node.href) {
      html += '<a class="btn sm primary" href="' + node.href + '">Detayını Aç &rarr;</a>';
    }
    drawer.innerHTML = html;
  }

  window.pdResetGraph = function() {
    scale = 1.0;
    panX = 0;
    panY = 0;
    selectedNode = null;
    updateInspector(null);
    render();
  };

  window.pdFilterGraph = function(selectEl) {
    var rel = selectEl.value;
    var url = '/api/graph/data' + (rel ? '?relation=' + rel : '');
    fetch(url).then(function(r){ return r.json(); }).then(function(data){
      showGraph(data, rel);
    });
  };

  window.pdAction('reset-graph', window.pdResetGraph);
  window.pdAction('filter-graph', window.pdFilterGraph);

  // Boş ağda gri, sessiz bir tuval kullanıcıya hiçbir şey söylemiyordu: neden boş olduğu
  // ve ne zaman dolacağı yazılır. Filtreli görünümde boşluk başka bir anlam taşır.
  function showGraph(data, rel) {
    var empty = document.getElementById('pd-graph-empty');
    var none = !data || !data.nodes || data.nodes.length === 0;
    if (empty) {
      empty.hidden = !none;
      var msg = empty.querySelector('[data-empty-msg]');
      if (msg) msg.textContent = rel
        ? 'Bu ilişki türünde henüz bağlantı yok. Filtreyi "Tüm İlişkiler" yapın.'
        : 'Henüz ilişki kurulmadı. Siyasi hafıza adımı aktörleri, beyanları ve olayları bağladığında ağ burada görünür.';
    }
    if (canvas) canvas.style.display = none ? 'none' : 'block';
    if (!none) initSimulation(data);
  }

  fetch('/api/graph/data').then(function(r){ return r.json(); }).then(function(data){
    showGraph(data, '');
  });
})();
"""


@router.get("/graph", response_class=HTMLResponse)
@router.get("/graf", response_class=HTMLResponse)
def graph_page() -> HTMLResponse:
    """Etkileşimli Siyasi İlişki ve İstihbarat Grafiği sayfası."""
    data = get_graph_data(limit_nodes=45)
    stats = data["stats"]

    body = f"""
{
        page_head(
            "Siyasi İlişki ve İstihbarat Grafı",
            lede="Aktörler, vaatler, Meclis oylamaları ve söylem zıtlıkları arasındaki deterministik bağlantı ağı.",
            badges='<span class="badge ok">Canlı Ağ</span>',
            actions=f'<button class="btn sm ghost" type="button"{action_attrs("reset-graph")}>'
            f'{icon("refresh", 13)}<span>Merkeze Al</span></button>',
        )
    }

<div class="kpis" style="margin-bottom:var(--space-6)">
  {kpi("Ağ Düğümleri", fmt.number(stats["node_count"]), unit="öğe", icon_name="grid")}
  {kpi("İlişki Bağlantıları", fmt.number(stats["link_count"]), unit="bağ", icon_name="link")}
  {kpi("Söylem Zıtlığı", fmt.number(stats["shift_count"]), unit="tespit", icon_name="warning")}
</div>

<div class="split" style="grid-template-columns: 1fr 280px; gap: var(--space-4);">
  <div class="stack">
    <div style="background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-lg);overflow:hidden;position:relative">
      <div style="position:absolute;top:12px;left:12px;z-index:5;display:flex;gap:8px;background:var(--color-surface);padding:6px 12px;border-radius:var(--radius-md);border:1px solid var(--color-border)">
        <span class="subtle" style="font-size:var(--text-xs);align-self:center">Filtre:</span>
        <select class="input sm" style="width:auto"{action_attrs("filter-graph", event="change")}>
          <option value="">Tüm İlişkiler</option>
          <option value="reversal">U-Dönüşü / Zıtlık</option>
          <option value="broken_promise">Tutulmayan Vaat</option>
          <option value="updates">Güncelleme / Takip</option>
          <option value="same_thread">Aynı Gelişme Akışı</option>
        </select>
      </div>

      <canvas id="pd-graph-canvas" width="960" height="580" style="display:block;width:100%;height:auto;cursor:grab;background:var(--color-surface-sunken)"></canvas>
      <div id="pd-graph-empty" hidden style="padding:var(--space-8) var(--space-6);text-align:center;background:var(--color-surface-sunken)">
        <p style="margin:0 0 var(--space-2);font-weight:var(--weight-semibold);color:var(--color-fg)">{icon("graph", 16)} İlişki ağı boş</p>
        <p class="subtle" data-empty-msg style="margin:0 auto;max-width:52ch;font-size:var(--text-sm)"></p>
      </div>
    </div>
    <p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">
      {icon("info", 12)} Sürükleyerek gezinebilir, tekerlek ile yakınlaştırabilir ve detayını görmek için düğümlere tıklayabilirsiniz.
    </p>
  </div>

  <div class="stack">
    {
        card(
            '<div id="node-inspector"><p class="subtle" style="margin:0">İncelemek istediğiniz düğüme tıklayın.</p></div>',
            title="Düğüm Detayı",
            actions='<span class="subtle" style="font-size:var(--text-xs)">canlı istihbarat</span>',
        )
    }

    {
        card(
            '<ul style="margin:0;padding:0;list-style:none;font-size:var(--text-xs);line-height:1.8">'
            '<li><span style="color:var(--color-chart-1)">●</span> <b>Mavi:</b> Siyasi Aktör (Bakan / Lider)</li>'
            '<li><span style="color:var(--color-chart-2)">●</span> <b>Mor:</b> Geçmiş Beyan / Vaat</li>'
            '<li><span style="color:var(--color-chart-3)">●</span> <b>Açık Mavi:</b> Güncel İcraat / Olay</li>'
            '<li><span style="color:var(--color-contra)">─</span> <b>Kırmızı Çizgi:</b> Çelişki / U-Dönüşü</li>'
            '<li><span style="color:var(--color-accent)">─</span> <b>Vurgu Çizgisi:</b> Gelişme / Takip</li>'
            '</ul>',
            title="Graf Lejantı",
        )
    }
  </div>
</div>
"""

    return HTMLResponse(
        page(
            "İlişki Grafı",
            body,
            active="/graph",
            crumbs=(("Çalışma Masası", None), ("İlişki Grafı", None)),
            extra_js=ACTIVITY_JS + _GRAPH_JS,
        )
    )
