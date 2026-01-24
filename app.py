import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from io import BytesIO
import os
from PIL import Image
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, Alignment

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inducor - Diagnóstico IEEE 400.2", layout="wide")

# --- PALETA DE COLORES ---
COLORES_ABANICO = [
    "#FFFF00", "#0D47A1", "#2979FF", "#00B0FF", "#00C853", 
    "#64DD17", "#AEEA00", "#FFD600", "#FF6D00", "#D50000", "#212121"
]
COLOR_TRAZA_MEDICION = "#D50000"
COLOR_LINEA_PUNTEADA = "#81C784"
LOGO_PATH = "logo_inducor.png"

# --- FUNCIONES TÉCNICAS AUXILIARES ---

def obtener_niveles_kv(u_nominal):
    if u_nominal == 0: return 0.0, 0.0, 0.0, 0.0
    uo = round(u_nominal / (3**0.5), 2)
    return uo, round(uo * 0.5, 2), round(uo * 1.0, 2), round(uo * 1.5, 2)

def generar_eje_x_hibrido(voltajes):
    """Calcula los ticks del eje X mezclando enteros y valores exactos."""
    min_x = int(np.floor(voltajes[0])) - 1
    max_x = int(np.ceil(voltajes[2])) + 1
    ticks_enteros = list(range(max(0, min_x), max_x + 1))
    
    ticks_filtrados = []
    for t in ticks_enteros:
        es_conflictivo = False
        for v in voltajes:
            if abs(t - v) < 0.8:
                es_conflictivo = True
                break
        if not es_conflictivo:
            ticks_filtrados.append(t)

    todos_ticks = sorted(list(set(ticks_filtrados + voltajes)))
    textos_ticks = []
    for t in todos_ticks:
        if t in voltajes:
            textos_ticks.append(f"<b>{t:.2f}</b>")
        else:
            textos_ticks.append(str(int(t)))
            
    return todos_ticks, textos_ticks

def agregar_logo_seguro(fig, x_pos, y_pos, x_anchor):
    if os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH)
            fig.add_layout_image(dict(
                source=img, xref="paper", yref="paper", 
                x=x_pos, y=y_pos, 
                sizex=0.20 if x_anchor=="left" else 0.25, 
                sizey=0.20 if x_anchor=="left" else 0.25, 
                xanchor=x_anchor, yanchor="bottom"
            ))
        except Exception:
            pass

# --- GESTIÓN DE ESTADO ---
if 'td_05' not in st.session_state: st.session_state.td_05 = 0.0
if 'td_15' not in st.session_state: st.session_state.td_15 = 0.0
if 'u0_medido' not in st.session_state: st.session_state.u0_medido = 0.0

def calcular_seguidor_05():
    st.session_state.td_05 = max(0.0, min(st.session_state.td_15 - 5.0, st.session_state.u0_medido))

def validar_limites_al_cambiar_uo():
    nuevo_min = float(st.session_state.u0_medido)
    nuevo_max = float(st.session_state.u0_medido + 5.0)
    if st.session_state.td_15 < nuevo_min: st.session_state.td_15 = nuevo_min
    if st.session_state.td_15 > nuevo_max: st.session_state.td_15 = nuevo_max
    calcular_seguidor_05()

# --- SIDEBAR ---
if os.path.exists(LOGO_PATH):
    try:
        st.sidebar.image(Image.open(LOGO_PATH), width=220)
    except Exception:
        st.sidebar.title("INDUCOR")
else:
    st.sidebar.title("INDUCOR")

u_linea = st.sidebar.number_input("Tensión Nominal (U) [kV]", min_value=0.0, value=0.0, step=0.1)

st.sidebar.number_input(
    "Tan Delta en Uo (1.0)", min_value=0.0, max_value=4.0, value=0.0, step=0.01, 
    key="u0_medido", on_change=validar_limites_al_cambiar_uo
)

if u_linea > 0:
    min_din = float(st.session_state.u0_medido)
    max_din = float(st.session_state.u0_medido + 5.0)
    st.sidebar.divider()
    mostrar_traza = st.sidebar.checkbox("Mostrar Medición (Traza Roja)", value=True)
    st.sidebar.slider("Tan Delta en 1.5 Uo (MAESTRO)", min_value=min_din, max_value=max_din, key='td_15', on_change=calcular_seguidor_05, step=0.01)
    st.sidebar.slider("Tan Delta en 0.5 Uo (SEGUIDOR)", 0.0, float(max(st.session_state.u0_medido, 0.1)), key='td_05', disabled=True, step=0.01)

# --- GRÁFICO 1: ABANICO ---
def crear_grafico_abanico(voltajes, u0_val, medicion_actual, mostrar_traza_roja, u_nom_sistema):
    fig = go.Figure()
    
    # Abanico
    pasos_abanico = np.arange(u0_val, u0_val + 5.5, 0.5)
    for i, v15_final in enumerate(reversed(pasos_abanico)):
        v05_inicio = max(0.0, v15_final - 5.0)
        idx_color = min(i, len(COLORES_ABANICO) - 1)
        fig.add_trace(go.Scatter(
            x=voltajes, y=[v05_inicio, u0_val, v15_final],
            mode='lines', line=dict(color=COLORES_ABANICO[idx_color], width=2),
            hoverinfo='skip', showlegend=False
        ))

    # --- ETIQUETAS SUPERIORES (Manuales para asegurar posición) ---
    rango_y_max = int(u0_val + 6)
    labels_superiores = ["0,5 U₀", "U₀", "1,5 U₀"]
    
    for i, kv in enumerate(voltajes):
        # Línea Vertical
        fig.add_vline(x=kv, line_dash="dash", line_color=COLOR_LINEA_PUNTEADA, line_width=2)
        # Etiqueta de Texto Arriba
        fig.add_annotation(
            x=kv, y=rango_y_max, 
            text=f"<b>{labels_superiores[i]}</b>", 
            showarrow=False, 
            yshift=10, # Un poco más arriba del límite del gráfico
            font=dict(size=14, color="black", family="Arial Black")
        )
        
    # Flechas de cotas (Valores numéricos de voltaje en las líneas)
    fig.add_annotation(x=voltajes[1], y=u0_val, text=f"<b>{u0_val:.2f}</b>", showarrow=True, arrowhead=2, arrowsize=1.5, ax=-60, ay=-30, font=dict(size=16, color="black"), arrowcolor="#424242")
    tope_teorico = u0_val + 5.0
    fig.add_annotation(x=voltajes[2], y=tope_teorico, text=f"<b>{tope_teorico:.2f}</b>", xanchor="right", showarrow=True, arrowhead=2, arrowsize=1.5, ax=-60, ay=-30, font=dict(size=16, color="black"), arrowcolor="#424242")

    if mostrar_traza_roja:
        fig.add_trace(go.Scatter(
            x=voltajes, y=medicion_actual,
            mode='lines+markers', name='MEDICIÓN ACTUAL',
            line=dict(color=COLOR_TRAZA_MEDICION, width=5),
            marker=dict(size=10, symbol='diamond', line=dict(width=2, color="white"))
        ))

    # Logo
    agregar_logo_seguro(fig, 1.0, -0.38, "right")

    ticks_vals, ticks_text = generar_eje_x_hibrido(voltajes)

    fig.update_layout(
        title=dict(text=f"<b>RESULTADO DE ENSAYO DE TG (δ)<br>CABLE DE MEDIA TENSIÓN ({u_nom_sistema}kV)</b>", x=0.5, xanchor='center', font=dict(size=18, color="black", family="Arial Black")),
        xaxis=dict(title=dict(text="<b>NIVELES DE TENSIÓN (kV)</b>", font=dict(color="black", size=14)), tickmode='array', tickvals=ticks_vals, ticktext=ticks_text, tickangle=0, gridcolor='rgba(0,0,0,0)', linecolor='black', mirror=True, tickfont=dict(size=11, color="black", family="Arial")),
        yaxis=dict(title=dict(text="<b>TG (δ) 1·10⁻³</b>", font=dict(color="black", size=14)), range=[0, rango_y_max], dtick=1, gridcolor='#E0E0E0', linecolor='black', mirror=True, tickfont=dict(size=12, color="black", family="Arial")),
        plot_bgcolor='white', paper_bgcolor='white', height=650, margin=dict(l=80, r=80, t=100, b=220), showlegend=False
    )
    return fig

# --- GRÁFICO 2: ÁREA SEGURA ---
def crear_grafico_area_segura(voltajes, medicion_actual, mostrar_traza_roja, u_nom_sistema):
    fig = go.Figure()
    
    u0_val = medicion_actual[1]
    techo_dinamico = u0_val + 5.0
    
    limites_zona_y = [u0_val, u0_val, techo_dinamico]
    
    # Zona Rellena
    fig.add_trace(go.Scatter(
        x=voltajes, y=limites_zona_y,
        mode='lines', line=dict(width=0),
        fill='tozeroy', fillcolor='rgba(255, 165, 0, 0.4)', name='ZONA SEGURA'
    ))

    # Línea Borde
    fig.add_trace(go.Scatter(
        x=voltajes, y=limites_zona_y,
        mode='lines', line=dict(color='orange', width=3, dash='solid'), showlegend=False
    ))

    # --- ETIQUETAS NUMÉRICAS EN NEGRO (CORREGIDO) ---
    # Inicio (0.5 Uo)
    fig.add_annotation(
        x=voltajes[0], y=u0_val,
        text=f"<b>{u0_val:.2f}</b>",
        xanchor="right", yanchor="bottom",
        showarrow=False, 
        font=dict(color="black", size=14, family="Arial Black"), # <--- AHORA ES NEGRO
        yshift=5, xshift=-5
    )
    # Final (1.5 Uo)
    fig.add_annotation(
        x=voltajes[2], y=techo_dinamico,
        text=f"<b>{techo_dinamico:.2f}</b>",
        xanchor="left", yanchor="bottom",
        showarrow=False, 
        font=dict(color="black", size=14, family="Arial Black"), # <--- AHORA ES NEGRO
        yshift=5, xshift=5
    )

    # Texto Central Inteligente
    x_texto = (voltajes[1] + voltajes[2]) / 2 
    y_texto = (u0_val + 2.5) / 2
    fig.add_annotation(
        x=x_texto, y=y_texto,
        text="<b>IEEE400.2 MERIT AREA:<br>NO ACTION REQUIRED</b>",
        showarrow=False, font=dict(size=14, color="black", family="Arial Black"),
        align="center", bgcolor="rgba(255, 255, 255, 0.5)", bordercolor="black", borderwidth=1
    )

    if mostrar_traza_roja:
        fig.add_trace(go.Scatter(
            x=voltajes, y=medicion_actual,
            mode='lines+markers', name='MEDICIÓN ACTUAL',
            line=dict(color=COLOR_TRAZA_MEDICION, width=4),
            marker=dict(size=10, symbol='diamond', line=dict(width=2, color="white"))
        ))
    
    # --- ETIQUETAS SUPERIORES EN GRÁFICO DE ÁREA TAMBIÉN ---
    max_y_view = max(10, techo_dinamico + 1)
    labels_superiores = ["0,5 U₀", "U₀", "1,5 U₀"]
    
    for i, kv in enumerate(voltajes):
        fig.add_vline(x=kv, line_dash="dash", line_color=COLOR_LINEA_PUNTEADA, line_width=2)
        fig.add_annotation(
            x=kv, y=max_y_view, 
            text=f"<b>{labels_superiores[i]}</b>", 
            showarrow=False, 
            yshift=10, 
            font=dict(size=14, color="black", family="Arial Black")
        )
        
    # Logo
    agregar_logo_seguro(fig, 1.0, -0.38, "right")

    ticks_vals, ticks_text = generar_eje_x_hibrido(voltajes)
    titulo_largo = f"TAN DELTA ON {u_nom_sistema}KV CLASS CABLE - NO ACTION GRAPHIC AREA FOR:<br>U₀≤4·10⁻³ & [Tgδ@1.5U₀ – Tgδ@0.5U₀]≤1.5x10⁻³"

    fig.update_layout(
        title=dict(text=f"<b>{titulo_largo}</b>", x=0.5, xanchor='center', font=dict(size=14, color="black", family="Arial")),
        xaxis=dict(title=dict(text="<b>NIVELES DE TENSIÓN (kV)</b>", font=dict(color="black", size=14)), tickmode='array', tickvals=ticks_vals, ticktext=ticks_text, tickangle=0, gridcolor='rgba(0,0,0,0)', linecolor='black', mirror=True, tickfont=dict(size=11, color="black")),
        yaxis=dict(title=dict(text="<b>TG (δ) 1·10⁻³</b>", font=dict(color="black", size=14)), range=[0, max_y_view], dtick=1, gridcolor='white', linecolor='black', mirror=True, tickfont=dict(size=12, color="black")),
        plot_bgcolor='white', paper_bgcolor='white', height=600, margin=dict(l=80, r=80, t=100, b=220), showlegend=False
    )
    return fig

# --- RENDERIZADO PRINCIPAL ---
uo_v, kv_05, kv_10, kv_15 = obtener_niveles_kv(u_linea)
voltajes_x = [kv_05, kv_10, kv_15]
medicion_y = [st.session_state.td_05, st.session_state.u0_medido, st.session_state.td_15]

if u_linea > 0:
    try:
        tab1, tab2 = st.tabs(["Análisis de Tendencia", "Área de Seguridad"])
        with tab1:
            fig_abanico = crear_grafico_abanico(voltajes_x, st.session_state.u0_medido, medicion_y, mostrar_traza, u_linea)
            st.plotly_chart(fig_abanico, use_container_width=True)
        with tab2:
            fig_area = crear_grafico_area_segura(voltajes_x, medicion_y, mostrar_traza, u_linea)
            st.plotly_chart(fig_area, use_container_width=True)
    except Exception as e:
        st.error(f"Error al generar gráficos: {e}")

# --- EXPORTACIÓN ---
def exportar_excel_completo(fig_abanico, fig_area, u0_sel):
    output = BytesIO()
    try:
        img_abanico = fig_abanico.to_image(format="png", width=1400, height=800, scale=2)
        img_area = fig_area.to_image(format="png", width=1400, height=800, scale=2)
    except Exception:
        return None
    
    combinaciones = []
    for v15 in np.arange(u0_sel, u0_sel + 5.5, 0.5)[::-1]:
        combinaciones.append({
            "0,5·U0": round(max(0.0, v15-5.0), 2), 
            "U0": round(u0_sel, 2), 
            "1,5·U0": round(v15, 2)
        })
    df = pd.DataFrame(combinaciones)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte', startrow=1, startcol=1)
        ws = writer.sheets['Reporte']
        for row in ws.iter_rows(min_row=2, max_row=2, min_col=2, max_col=4):
            for cell in row: cell.font = Font(bold=True); cell.alignment = Alignment(horizontal='center')
        ws.add_image(OpenpyxlImage(BytesIO(img_abanico)), 'B18')
        ws.add_image(OpenpyxlImage(BytesIO(img_area)), 'B60')
    return output.getvalue()

if u_linea > 0:
    if st.sidebar.button("📦 Generar Informe de Ingeniería"):
        archivo = exportar_excel_completo(fig_abanico, fig_area, st.session_state.u0_medido)
        if archivo:
            st.sidebar.download_button("⬇️ Descargar Reporte Completo (.xlsx)", data=archivo, file_name=f"Informe_Inducor_{u_linea}kV.xlsx")
        else:

            st.sidebar.error("Error al generar Excel.")
