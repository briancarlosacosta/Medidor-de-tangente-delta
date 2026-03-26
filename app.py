import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from io import BytesIO
import os
from PIL import Image
from typing import Tuple, List
import imageio

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================

class Config:
    PAGE_TITLE = "Inducor - Diagnóstico Fluido IEEE 400.2"
    LOGO_PATH = "logo_inducor.png" 
    COLOR_MEASURED = "#D50000" # Rojo Inducor
    # Amarillo institucional de Inducor semi-transparente
    COLOR_AREA_FILL = "rgba(245, 182, 22, 0.4)" 

st.set_page_config(page_title=Config.PAGE_TITLE, layout="wide")

# ==========================================
# INICIALIZACIÓN DE ESTADOS Y GATILLO
# ==========================================

# Variables de estado para la pestaña Tendencia
if 'm_10_tendencia' not in st.session_state: st.session_state['m_10_tendencia'] = 4.0
if 'm_05_tendencia' not in st.session_state: st.session_state['m_05_tendencia'] = 4.0
if 'm_15_tendencia' not in st.session_state: st.session_state['m_15_tendencia'] = 9.0

# Variables de estado para la pestaña Área No Action
if 'm_10_noaction' not in st.session_state: st.session_state['m_10_noaction'] = 4.0
if 'm_05_noaction' not in st.session_state: st.session_state['m_05_noaction'] = 4.0
if 'm_15_noaction' not in st.session_state: st.session_state['m_15_noaction'] = 9.0

def sync_mediciones_tendencia():
    m10 = st.session_state['m_10_tendencia']
    st.session_state['m_05_tendencia'] = float(m10)
    st.session_state['m_15_tendencia'] = float(m10 + 5.0)

def sync_mediciones_noaction():
    m10 = st.session_state['m_10_noaction']
    st.session_state['m_05_noaction'] = float(m10)
    st.session_state['m_15_noaction'] = float(m10 + 5.0)

# ==========================================
# 2. LÓGICA DE CÁLCULO
# ==========================================

def calculate_voltages(u_nominal: float) -> Tuple[float, float, float]:
    if u_nominal == 0: return 0.0, 0.0, 0.0
    uo = round(u_nominal / (3**0.5), 2)
    return round(uo * 0.5, 2), uo, round(uo * 1.5, 2)

def get_ticks_labels(voltage_values: list):
    v05, v10, v15 = voltage_values
    ticks = [v05, v10, v15]
    labels = [
        f"<b>{str(v05).replace('.', ',')}</b><br>0.5 U₀", 
        f"<b>{str(v10).replace('.', ',')}</b><br>U₀", 
        f"<b>{str(v15).replace('.', ',')}</b><br>1.5 U₀"
    ]
    return ticks, labels

# ==========================================
# NUEVO: MOTOR DE GENERACIÓN DE GIF
# ==========================================

def generate_gif_from_frames(base_fig: go.Figure, frames) -> bytes:
    """
    Renderiza los fotogramas de Plotly en imágenes estáticas 
    y los compila en un archivo GIF en memoria con alta fluidez.
    """
    # Convertimos explícitamente a lista para evitar el error de la tupla
    frames = list(frames)
    
    # Si no hay frames (ej. barrido desactivado), generamos un GIF de 1 fotograma
    if not frames:
        temp_fig = go.Figure(base_fig)
        temp_fig.update_layout(updatemenus=[])
        img_bytes = temp_fig.to_image(format="png", width=1200, height=700, scale=1)
        
        gif_bytes = BytesIO()
        try:
            img = imageio.v2.imread(img_bytes)
        except AttributeError:
            img = imageio.imread(img_bytes)
            
        imageio.mimsave(gif_bytes, [img], format='GIF', duration=500)
        return gif_bytes.getvalue()

    images = []
    # step = 1 siempre para garantizar la fluidez original (sin omitir frames)
    step = 1 
    selected_frames = list(frames[::step]) 
    
    if frames[-1] not in selected_frames:
        selected_frames.append(frames[-1]) 

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, frame in enumerate(selected_frames):
        status_text.text(f"Generando fotograma {i+1} de {len(selected_frames)}...")
        
        temp_fig = go.Figure(base_fig)
        
        # Aplicar los datos del frame actual a la figura
        for j, trace_data in enumerate(frame.data):
            trace_index = frame.traces[j]
            if hasattr(trace_data, 'x') and trace_data.x is not None:
                temp_fig.data[trace_index].x = trace_data.x
            if hasattr(trace_data, 'y') and trace_data.y is not None:
                temp_fig.data[trace_index].y = trace_data.y
            if hasattr(trace_data, 'visible'):
                temp_fig.data[trace_index].visible = trace_data.visible
            # Hacemos que también copie los textos en cada fotograma
            if hasattr(trace_data, 'text') and trace_data.text is not None:
                temp_fig.data[trace_index].text = trace_data.text
        
        # Copiamos también las anotaciones del fotograma para que salga el cartel en el GIF
        if hasattr(frame, 'layout') and hasattr(frame.layout, 'annotations'):
            temp_fig.layout.annotations = frame.layout.annotations

        temp_fig.update_layout(updatemenus=[]) 
        
        # Extraer imagen estática
        img_bytes = temp_fig.to_image(format="png", width=1200, height=700, scale=1)
        
        try:
            images.append(imageio.v2.imread(img_bytes))
        except AttributeError:
            images.append(imageio.imread(img_bytes))
            
        progress_bar.progress((i + 1) / len(selected_frames))

    status_text.text("Ensamblando GIF...")
    
    gif_bytes = BytesIO()
    # duration = 33 ms (~30 frames por segundo) para igualar la simulación web
    imageio.mimsave(gif_bytes, images, format='GIF', duration=33, loop=0)
    
    status_text.empty()
    progress_bar.empty()
    
    return gif_bytes.getvalue()

# ==========================================
# 3. MOTOR GRÁFICO (PLOTLY ANIMADO)
# ==========================================

class ChartBuilder:

    @staticmethod
    def _add_logos(fig: go.Figure):
        if os.path.exists(Config.LOGO_PATH):
            try:
                img = Image.open(Config.LOGO_PATH)
                fig.add_layout_image(dict(
                    source=img, xref="paper", yref="paper", x=1.0, y=-0.12, sizex=0.22, sizey=0.22, xanchor="right", yanchor="top", opacity=1
                ))
            except: pass

    @staticmethod
    def _add_dynamic_titles_and_axis(fig: go.Figure, title_text: str, x_ticks: list, x_labels: list, num_steps: int = 50, y_max: float = 10.0, y_dtick: float = 1.0):
        loop_sequence = [str(i) for i in range(num_steps)] * 100
        
        fig.update_layout(
            title=dict(text=f"<b>{title_text}</b>", x=0.5, xanchor='center', font=dict(size=16, family="Arial Black", color="black"), y=0.88),
            xaxis=dict(title="<b>NIVELES DE TENSION (kV)</b>", tickmode='array', tickvals=x_ticks, ticktext=x_labels, mirror=True, linecolor='black', showgrid=False),
            yaxis=dict(title="<b>TG (δ) 1·10⁻³</b>", range=[0, y_max], dtick=y_dtick, gridcolor='#E0E0E0', mirror=True, linecolor='black'),
            yaxis2=dict(range=[0, y_max], dtick=y_dtick, overlaying='y', side='right', showgrid=False, showline=False, tickfont=dict(color="black")),
            plot_bgcolor='white', paper_bgcolor='white', height=700, margin=dict(l=80, r=80, t=180, b=180), showlegend=False,
            
            updatemenus=[{
                "buttons": [
                    {"args": [loop_sequence, {"frame": {"duration": 30, "redraw": False}, "fromcurrent": True, "transition": {"duration": 30, "easing": "linear"}}], "label": "▶ PLAY", "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏸ PAUSE", "method": "animate"},
                    {"args": [["0"], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏹ STOP", "method": "animate"}
                ],
                "direction": "left", "pad": {"r": 10, "t": 10}, "showactive": False, "type": "buttons", "x": 0.05, "xanchor": "left", "y": -0.15, "yanchor": "top"
            }]
        )
        if len(x_ticks) > 0:
            fig.add_trace(go.Scatter(x=[x_ticks[0]], y=[0], mode='none', showlegend=False, yaxis='y2', hoverinfo='skip'))

    @staticmethod
    def _generate_sequential_frames_tendencia(v_points, measured_y, base_y, num_frames, trace_indices, show_sweep):
        m_05, m_10, m_15 = measured_y
        b_05, b_10, b_15 = base_y
        
        frames = []
        for i in range(num_frames):
            p = i / (num_frames - 1)  
            
            curr_05 = b_05 + p * (m_05 - b_05)
            curr_10 = b_10 + p * (m_10 - b_10)
            curr_15 = b_15 + p * (m_15 - b_15)
            
            x_fill = [v_points[0], v_points[1], v_points[2], v_points[2], v_points[0]]
            y_fill = [curr_05, curr_10, curr_15, 0.0, 0.0]
            
            x_line = [v_points[0], v_points[1], v_points[2]]
            y_line = [curr_05, curr_10, curr_15]

            frame_data = [
                go.Scatter(
                    x=x_fill, y=y_fill,
                    fillcolor=Config.COLOR_AREA_FILL,
                    visible=True 
                ),
                go.Scatter(x=x_line, y=y_line, mode='lines+markers', visible=True)
            ]
            frames.append(go.Frame(data=frame_data, name=str(i), traces=trace_indices))
            
        return frames

    @staticmethod
    def draw_fan_animated(v_points, u0_measured, u_nominal, measured_y, y_max=10.0, y_dtick=1.0, x_dtick=1.0, show_fan=True, show_sweep=True):
        fig = go.Figure()
        num_frames = 50
        
        color_map = {
            5.0: '#FFFF00', # Amarillo
            4.5: '#1F3864', # Azul Marino
            4.0: '#2F5597', # Azul Claro
            3.5: '#00B050', # Verde Oscuro
            3.0: '#92D050', # Verde Claro
            2.5: '#FF0000', # Rojo
            2.0: '#FFC000', # Naranja/Dorado
            1.5: '#FF0000', # Rojo
            1.0: '#1F3864', # Azul Marino
            0.5: '#2F5597', # Azul Claro
            0.0: '#1F3864'  # Azul Marino
        }

        comportamiento_tablas = {
            4.0: [4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0, 0.0, 0.0],
            3.0: [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
            2.0: [2.0, 1.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            1.0: [1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            0.0: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        }

        closest_u0 = min(comportamiento_tablas.keys(), key=lambda k: abs(k - u0_measured))
        valores_05_uo = comportamiento_tablas[closest_u0]

        steps = np.arange(0.0, 5.5, 0.5) 
        
        for idx, d in enumerate(steps):
            v15_y = u0_measured + d
            idx_lista = 10 - idx
            v05_y = valores_05_uo[idx_lista]
            
            x_vals = [v_points[0], v_points[1], v_points[2]]
            y_vals = [v05_y, u0_measured, v15_y]
                
            fig.add_trace(go.Scatter(
                x=x_vals, y=y_vals, mode='lines', 
                line=dict(color=color_map.get(d, 'black'), width=1.5), 
                hoverinfo='skip',
                visible=show_fan
            ))

        idx_fill = len(fig.data)
        idx_line = idx_fill + 1

        b_10 = u0_measured
        b_15 = u0_measured + 0.0 
        b_05 = max(0.0, b_15 - 5.0) 
        base_y = [b_05, b_10, b_15]

        x_fill_init = [v_points[0], v_points[1], v_points[2], v_points[2], v_points[0]]
        y_fill_init = [b_05, b_10, b_15, 0.0, 0.0]
            
        x_line_init = [v_points[0], v_points[1], v_points[2]]
        y_line_init = [b_05, b_10, b_15]

        fig.add_trace(go.Scatter(
            x=x_fill_init, y=y_fill_init, 
            mode='lines', line=dict(width=0),
            fill='toself', fillcolor=Config.COLOR_AREA_FILL, 
            hoverinfo='skip', visible=show_sweep
        ))
        
        fig.add_trace(go.Scatter(
            x=x_line_init, y=y_line_init, 
            mode='lines+markers', 
            line=dict(color=Config.COLOR_MEASURED, width=3),
            marker=dict(size=1, opacity=0), # Totalmente invisible para no alterar el diseño
            hoverinfo='skip', visible=show_sweep
        ))

        if show_sweep:
            frames = ChartBuilder._generate_sequential_frames_tendencia(
                v_points, measured_y, base_y, num_frames, [idx_fill, idx_line], show_sweep
            )
            fig.frames = frames
        else:
            fig.frames = []

        for v in v_points:
            fig.add_vline(x=v, line_width=1.5, line_dash="dash", line_color="#B4C6A6", opacity=0.8)

        labels_u = ['0,5 Uo', 'Uo', '1,5 Uo']
        for i, v in enumerate(v_points):
            fig.add_annotation(
                x=v, y=1.0, xref="x", yref="paper",
                text=f"{labels_u[i]}", showarrow=False, font=dict(size=14, color="#333333"),
                xanchor="left", xshift=10, yanchor="top", yshift=-10
            )

        u0_int = int(u0_measured) if u0_measured.is_integer() else u0_measured
        
        fig.add_annotation(
            x=v_points[1],    
            y=u0_measured,    
            text=f"AREA DE CUMPLIMIENTO \"NO ACTION\" PARA Uo= {u0_int}",
            showarrow=True, 
            arrowhead=0, 
            arrowcolor="#A6A6A6", 
            arrowwidth=1.5,
            ax=-150,    
            ay=-60,     
            font=dict(color="white", size=11, family="Arial"),
            bgcolor="#0055D4", 
            bordercolor="#0055D4", 
            borderpad=4
        )

        fig.add_annotation(
            x=v_points[0], y=u0_measured, text=f"{u0_int}",
            showarrow=True, arrowhead=0, arrowcolor="#B0B0B0",
            ax=-20, ay=-20, font=dict(color="#666666", size=10) 
        )
        
        y_max_fan = u0_measured + 5.0
        y_max_int = int(y_max_fan) if y_max_fan.is_integer() else y_max_fan
        fig.add_annotation(
            x=v_points[2], y=y_max_fan, text=f"{y_max_int}",
            showarrow=True, arrowhead=0, arrowcolor="#B0B0B0",
            ax=-20, ay=-20, font=dict(color="#666666", size=10)
        )

        title_text = f"RESULTADO DE ENSAYO DE TG (δ)<br><span style='font-size:12px'>CABLE DE MEDIA TENSION ({u_nominal}kV)</span>"
        
        ticks_v, ticks_l = get_ticks_labels(v_points)
        ChartBuilder._add_dynamic_titles_and_axis(fig, title_text, ticks_v, ticks_l, num_frames, y_max, y_dtick)
        
        fig.update_layout(
            separators=",.", 
            title=dict(text=title_text, font=dict(family="Arial", size=14), y=0.92),
            xaxis=dict(
                title="<b>NIVELES DE TENSION<br>(kV)</b>",
                tickmode='linear', dtick=x_dtick, tickformat=",.1f", 
                showgrid=False, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickfont=dict(color="#666666")
            ),
            yaxis=dict(
                title="<b>TG (δ)<br>1·10⁻³</b>", 
                range=[0, y_max], 
                showgrid=True, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickformat=",.1f", tickfont=dict(color="#666666")
            ),
            yaxis2=dict(
                range=[0, y_max], 
                tickformat=",.1f", tickfont=dict(color="#666666"), linecolor='#CCCCCC'
            ),
            margin=dict(t=120)
        )
        ChartBuilder._add_logos(fig)
        return fig

    @staticmethod
    def draw_area_shifting_demo(v_points, u_nominal, m_y_start, u0_end, ref_delta_pivot, y_max=10.0, y_dtick=1.0, x_dtick=1.0, show_limit_line=False, show_sweep=True):
        """Gráfico de Área No Action con la corrección para ZOOM aplicada"""
        fig = go.Figure()
        num_frames = 50
        
        u0_start = m_y_start[1] 
        
        # --- TRAZA 0: Limites del area (Punteada o Invisible) ---
        area_limits_initial = [u0_start, u0_start, u0_start + (ref_delta_pivot * 0.5)]
        if show_limit_line:
            limit_labels_ini = [f"<b>{val:.1f}</b>".replace('.', ',') for val in area_limits_initial]
            fig.add_trace(go.Scatter(x=v_points, y=area_limits_initial, mode='lines+markers+text', line=dict(color='black', width=2, dash='dash'), marker=dict(size=12, symbol='diamond', color='white', line=dict(width=2, color='black')), text=limit_labels_ini, textposition="top center", hoverinfo='skip'))
        else:
            fig.add_trace(go.Scatter(x=v_points, y=area_limits_initial, mode='lines', line=dict(color='rgba(0,0,0,0)'), hoverinfo='skip'))

        # --- TRAZA 1: Marcadores con valores respetando toggle ---
        y_exact_labels = [f"<b>{val:.1f}</b>".replace('.', ',') for val in m_y_start]
        fig.add_trace(go.Scatter(x=v_points, y=m_y_start, mode='markers+text', text=y_exact_labels, textposition="top center", marker=dict(size=12, symbol='diamond', color='white', line=dict(width=2, color='black')), hoverinfo='skip', visible=show_sweep))
        
        # --- TRAZA 2: Relleno Verde Rayado respetando toggle ---
        x_fill_init = [v_points[0], v_points[1], v_points[2], v_points[2], v_points[0]]
        y_fill_init = [m_y_start[0], m_y_start[1], m_y_start[2], 0.0, 0.0]
        
        fig.add_trace(go.Scatter(
            x=x_fill_init, y=y_fill_init, mode='lines', fill='toself', line=dict(width=0),
            fillcolor=Config.COLOR_AREA_FILL, 
            hoverinfo='skip', visible=show_sweep
        ))

        # --- TRAZA 3: Linea Roja separada para la animación ---
        fig.add_trace(go.Scatter(
            x=v_points, y=m_y_start, mode='lines', 
            line=dict(color=Config.COLOR_MEASURED, width=3), hoverinfo='skip', visible=show_sweep
        ))

        # --- MOTOR DE FOTOGRAMAS ---
        frames = []
        for i in range(num_frames):
            progress = i / (num_frames - 1)
            curr_u0 = u0_start + (u0_end - u0_start) * progress
            
            curr_m_y = [curr_u0, curr_u0, curr_u0 + 5.0]
            curr_area = [curr_u0, curr_u0, curr_u0 + (ref_delta_pivot * 0.5)]
            
            x_fill = [v_points[0], v_points[1], v_points[2], v_points[2], v_points[0]]
            y_fill = [curr_m_y[0], curr_m_y[1], curr_m_y[2], 0.0, 0.0]
            
            frame_data = []
            
            # Actualizamos Traza 0 (Limites)
            if show_limit_line:
                curr_lim_labels = [f"<b>{val:.1f}</b>".replace('.', ',') for val in curr_area]
                frame_data.append(go.Scatter(x=v_points, y=curr_area, text=curr_lim_labels))
            else:
                frame_data.append(go.Scatter(x=v_points, y=curr_area))
                
            # Actualizamos Traza 1 (Marcadores)
            curr_m_labels = [f"<b>{val:.1f}</b>".replace('.', ',') for val in curr_m_y]
            frame_data.append(go.Scatter(x=v_points, y=curr_m_y, text=curr_m_labels, visible=True))
            
            # Actualizamos Traza 2 (Relleno Rayado)
            frame_data.append(go.Scatter(
                x=x_fill, y=y_fill, 
                visible=True
            )) 
            
            # Actualizamos Traza 3 (Línea roja - ahora acompaña al relleno)
            frame_data.append(go.Scatter(x=v_points, y=curr_m_y, visible=True))
            
            frames.append(go.Frame(data=frame_data, name=str(i), traces=[0, 1, 2, 3]))

        if show_sweep:
            fig.frames = frames
        else:
            fig.frames = []

        # --- Etiquetas 0,5 Uo, Uo, 1,5 Uo superiores igual que en Tendencia ---
        for v in v_points:
            fig.add_vline(x=v, line_width=1.5, line_dash="dash", line_color="#B4C6A6", opacity=0.8)

        labels_u = ['0,5 Uo', 'Uo', '1,5 Uo']
        for i, v in enumerate(v_points):
            fig.add_annotation(
                x=v, y=1.0, xref="x", yref="paper",
                text=f"{labels_u[i]}", showarrow=False, font=dict(size=14, color="#333333"),
                xanchor="left", xshift=10, yanchor="top", yshift=-10
            )

        title_text = (
            f"TAN DELTA ON {u_nominal}KV<br>"
            f"CLASS CABLE - NO ACTION GRAPHIC AREA FOR:<br>"
            f"U0 ≤ 4x10^-3 & [Tgδ@1.5U0 – Tgδ@0.5U0] ≤ {str(ref_delta_pivot).replace('.',',')}x10<sup>-3</sup>"
        )
        ticks_v, ticks_l = get_ticks_labels(v_points)
        ChartBuilder._add_dynamic_titles_and_axis(fig, title_text, ticks_v, ticks_l, num_frames, y_max, y_dtick)
        
        # --- Aplicación exacta del Layout (cuadrículas, ejes, fuentes) de Tendencia ---
        fig.update_layout(
            separators=",.", 
            title=dict(text=title_text, font=dict(family="Arial", size=14), y=0.92),
            xaxis=dict(
                title="<b>NIVELES DE TENSION<br>(kV)</b>",
                tickmode='linear', dtick=x_dtick, tickformat=",.1f", 
                showgrid=False, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickfont=dict(color="#666666")
            ),
            yaxis=dict(
                title="<b>TG (δ)<br>1·10⁻³</b>", 
                range=[0, y_max], 
                showgrid=True, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickformat=",.1f", tickfont=dict(color="#666666")
            ),
            yaxis2=dict(
                range=[0, y_max], 
                tickformat=",.1f", tickfont=dict(color="#666666"), linecolor='#CCCCCC'
            ),
            margin=dict(t=120)
        )

        ChartBuilder._add_logos(fig)
        
        return fig

# ==========================================
# 4. EXCEL
# ==========================================

def get_excel(voltages, measured, u_nom):
    output = BytesIO()
    df = pd.DataFrame({"Nivel": ["0.5 Uo", "Uo", "1.5 Uo"], "kV": voltages, "Tg Delta": measured})
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    return output.getvalue()

# ==========================================
# 5. MAIN UI Y AUTOMATIZACIÓN DE CAMPOS
# ==========================================

def main():
    if os.path.exists(Config.LOGO_PATH):
        try: st.sidebar.image(Image.open(Config.LOGO_PATH), width=220)
        except Exception: st.sidebar.title("INDUCOR")
    else: st.sidebar.title("INDUCOR")

    st.sidebar.header("Parámetros de Ensayo")
    u_linea = st.sidebar.number_input("Tensión Nominal (U) [kV]", min_value=0.0, value=33.0, step=0.1)
    v05_def, u0_def, v15_def = calculate_voltages(u_linea)

    with st.sidebar.expander("Ajuste eje X en kV", expanded=False):
        kv_start = st.number_input("Tensión Inicial (0.5 Uo)", value=v05_def, format="%.2f")
        kv_mid = st.number_input("Tensión Central (Uo)", value=u0_def, format="%.2f")
        kv_end = st.number_input("Tensión Final (1.5 Uo)", value=v15_def, format="%.2f")
        v_points = [kv_start, kv_mid, kv_end]
        x_dtick = st.number_input("Escala X (Saltos de)", min_value=0.1, value=1.0, step=0.5)

    with st.sidebar.expander("Ajuste eje Y (Tg δ)", expanded=False):
        y_max = st.number_input("Límite Superior Y", min_value=1.0, value=10.0, step=1.0)
        y_dtick = st.number_input("Escala Y (Saltos de)", min_value=0.1, value=1.0, step=0.5)

    # --- PESTAÑA: TENDENCIA ---
    with st.sidebar.expander("Configuración Gráfico Tendencia", expanded=False):
        u0_ref = st.number_input("Ajuste el pivote del grafico de tendencia", 0.0, 10.0, 4.0)
        mostrar_abanico = st.checkbox("Mostrar abanico histórico", value=True)
        mostrar_barrido_tend = st.checkbox("Mostrar barrido (área y recta)", value=True, key="chk_barrido_tend")
        
        st.subheader("Simulación")
        m_10_val_tendencia = st.number_input("Uo final", min_value=0.0, max_value=20.0, key='m_10_tendencia', step=0.1, on_change=sync_mediciones_tendencia)
        demo_u0_end_tendencia = st.number_input("Uo inicial", value=8.0, step=0.1, key="end_tendencia")

        m_05_calc_tendencia = float(m_10_val_tendencia)
        m_15_calc_tendencia = float(m_10_val_tendencia + 5.0)

        st.number_input("Medido @ 0.5 Uo (Automático)", value=m_05_calc_tendencia, disabled=True, key="05_tendencia")
        st.number_input("Medido @ 1.5 Uo (Automático)", value=m_15_calc_tendencia, disabled=True, key="15_tendencia")
        m_y_tendencia = [m_05_calc_tendencia, m_10_val_tendencia, m_15_calc_tendencia]


    # --- PESTAÑA: ÁREA NO ACTION ---
    with st.sidebar.expander("Configuración Zona No Action", expanded=False):
        st.write("Ajustes visuales del límite seguro.")
        p_delta_pivot = st.number_input("Delta Máximo Fijo (1.5Uo-0.5Uo)", value=9.0, step=0.1)
        mostrar_barrido_noact = st.checkbox("Mostrar barrido (área y recta)", value=True, key="chk_barrido_noact")
        
        st.subheader("Simulación")
        demo_u0_end_noaction = st.number_input("Uo final", value=4.0, step=0.1, key="end_noaction")
        m_10_val_noaction = st.number_input("Uo inicial", value=0.0, min_value=0.0, max_value=20.0, key='m_10_noaction', step=0.1, on_change=sync_mediciones_noaction)

        m_05_calc_noaction = float(m_10_val_noaction)
        m_15_calc_noaction = float(m_10_val_noaction + 5.0)

        st.number_input("Medido @ 0.5 Uo (Automático)", value=m_05_calc_noaction, disabled=True, key="05_noaction")
        st.number_input("Medido @ 1.5 Uo (Automático)", value=m_15_calc_noaction, disabled=True, key="15_noaction")
        
        m_y_start_anim = [float(m_10_val_noaction), float(m_10_val_noaction), float(m_10_val_noaction) + 5.0]
        u0_end_anim = float(demo_u0_end_noaction)


    if u_linea > 0:
        tab_fan, tab_area = st.tabs(["Tendencia ", "Área No Action"])
        
        with tab_fan:
            fig_fan = ChartBuilder.draw_fan_animated(
                v_points, u0_ref, u_linea, m_y_tendencia, 
                y_max=y_max, y_dtick=y_dtick, x_dtick=x_dtick, 
                show_fan=mostrar_abanico, show_sweep=mostrar_barrido_tend
            )
            # AÑADIDO: staticPlot=True para bloquear la interacción con el mouse
            st.plotly_chart(fig_fan, use_container_width=True, config={'staticPlot': True})

            if st.button("Generar y Descargar GIF (Tendencia)"):
                with st.spinner("Procesando GIF de Tendencia... esto tomará unos segundos."):
                    try:
                        gif_bytes = generate_gif_from_frames(fig_fan, fig_fan.frames)
                        st.download_button(
                            label="Descargar GIF Listo",
                            data=gif_bytes,
                            file_name="animacion_tendencia.gif",
                            mime="image/gif"
                        )
                    except Exception as e:
                        st.error(f"Error al generar GIF. Verifica tener instalados 'kaleido' e 'imageio'. Detalle: {e}")
            
        with tab_area:
            fig_area = ChartBuilder.draw_area_shifting_demo(
                v_points, u_linea, m_y_start_anim, u0_end_anim, p_delta_pivot, 
                y_max=y_max, y_dtick=y_dtick, x_dtick=x_dtick, show_limit_line=False, 
                show_sweep=mostrar_barrido_noact
            )
            # AÑADIDO: staticPlot=True para bloquear la interacción con el mouse
            st.plotly_chart(fig_area, use_container_width=True, config={'staticPlot': True})

            if st.button("Generar y Descargar GIF (Área No Action)"):
                with st.spinner("Procesando GIF de Área No Action... esto tomará unos segundos."):
                    try:
                        gif_bytes = generate_gif_from_frames(fig_area, fig_area.frames)
                        st.download_button(
                            label="Descargar GIF Listo",
                            data=gif_bytes,
                            file_name="animacion_area_no_action.gif",
                            mime="image/gif"
                        )
                    except Exception as e:
                        st.error(f"Error al generar GIF. Verifica tener instalados 'kaleido' e 'imageio'. Detalle: {e}")
            
        excel = get_excel(v_points, m_y_tendencia, u_linea) 
        st.sidebar.download_button("Descargar Reporte (.xlsx)", excel, f"Informe_Inducor_{u_linea}kV.xlsx")
    else:
        st.warning("Ingrese una Tensión Nominal válida para comenzar.")

if __name__ == "__main__":
    main()