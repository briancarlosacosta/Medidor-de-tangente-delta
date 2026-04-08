import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    PAGE_TITLE = "Tangente delta IEEE 400.2"
    LOGO_PATH = "logo_inducor.png" 
    COLOR_MEASURED = "#D50000" # Rojo Inducor
    
    # Colores institucionales
    COLOR_AREA_FILL = "rgba(245, 182, 22, 0.4)"  # Amarillo Inducor semi-transparente
    COLOR_BOX_05 = "#00B050" # Verde de los fasores e I
    COLOR_BOX_10 = "#0055D4" # Azul Inducor
    COLOR_BOX_15 = "#D50000" # Rojo Inducor
    COLOR_GREY_BOX = "#D3D9DF" # Tono gris para la inecuación

    DELTA_NO_ACTION = 1.5
    TITLE_FONT = dict(size=14, family="Arial Black", color="black")

st.set_page_config(page_title=Config.PAGE_TITLE, layout="wide")

# ==========================================
# INICIALIZACIÓN DE ESTADOS Y GATILLO
# ==========================================

if 'm_10_tendencia' not in st.session_state: st.session_state['m_10_tendencia'] = 4.0
if 'm_05_tendencia' not in st.session_state: st.session_state['m_05_tendencia'] = 4.0
if 'm_15_tendencia' not in st.session_state: st.session_state['m_15_tendencia'] = 9.0

if 'm_10_noaction' not in st.session_state: st.session_state['m_10_noaction'] = 0.0
if 'm_05_noaction' not in st.session_state: st.session_state['m_05_noaction'] = 0.0
if 'm_15_noaction' not in st.session_state: st.session_state['m_15_noaction'] = 5.0

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
    
    labels_stacked = [
        f"<b>{str(v05).replace('.', ',')}</b><br>0,5x10⁻³Uo", 
        f"<b>{str(v10).replace('.', ',')}</b><br>1,0x10⁻³Uo", 
        f"<b>{str(v15).replace('.', ',')}</b><br>1,5x10⁻³Uo"
    ]
    labels_flat = [str(v).replace('.', ',') for v in voltage_values]
    return ticks, labels_stacked, labels_flat

# ==========================================
# MOTOR DE GENERACIÓN DE GIF
# ==========================================

def generate_gif_from_frames(base_fig: go.Figure, frames) -> bytes:
    frames = list(frames)
    
    if not frames:
        temp_fig = go.Figure(base_fig)
        temp_fig.update_layout(updatemenus=[])
        img_bytes = temp_fig.to_image(format="png", width=1600, height=850, scale=2)
        
        gif_bytes = BytesIO()
        try:
            img = imageio.v2.imread(img_bytes)
        except AttributeError:
            img = imageio.imread(img_bytes)
            
        imageio.mimsave(gif_bytes, [img], format='GIF', duration=500)
        return gif_bytes.getvalue()

    images = []
    step = 1 
    selected_frames = list(frames[::step]) 
    
    if frames[-1] not in selected_frames:
        selected_frames.append(frames[-1]) 

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, frame in enumerate(selected_frames):
        status_text.text(f"Generando fotograma {i+1} de {len(selected_frames)}...")
        
        temp_fig = go.Figure(base_fig)
        
        for j, trace_data in enumerate(frame.data):
            trace_index = frame.traces[j]
            if hasattr(trace_data, 'x') and trace_data.x is not None:
                temp_fig.data[trace_index].x = trace_data.x
            if hasattr(trace_data, 'y') and trace_data.y is not None:
                temp_fig.data[trace_index].y = trace_data.y
            if hasattr(trace_data, 'visible'):
                temp_fig.data[trace_index].visible = trace_data.visible
            if hasattr(trace_data, 'text') and trace_data.text is not None:
                temp_fig.data[trace_index].text = trace_data.text
        
        if hasattr(frame, 'layout') and frame.layout is not None:
            if hasattr(frame.layout, 'annotations'):
                temp_fig.layout.annotations = frame.layout.annotations
            if hasattr(frame.layout, 'shapes'):
                temp_fig.layout.shapes = frame.layout.shapes

        temp_fig.update_layout(updatemenus=[]) 
        
        img_bytes = temp_fig.to_image(format="png", width=1600, height=850, scale=2)
        
        try:
            images.append(imageio.v2.imread(img_bytes))
        except AttributeError:
            images.append(imageio.imread(img_bytes))
            
        progress_bar.progress((i + 1) / len(selected_frames))

    status_text.text("Ensamblando GIF...")
    
    gif_bytes = BytesIO()
    imageio.mimsave(gif_bytes, images, format='GIF', duration=100, loop=0)
    
    status_text.empty()
    progress_bar.empty()
    
    return gif_bytes.getvalue()

# ==========================================
# 3. MOTOR GRÁFICO (PLOTLY ANIMADO)
# ==========================================

class ChartBuilder:

    @staticmethod
    def _add_logos(fig: go.Figure, x_pos=0.89, y_pos=-0.08):
        if os.path.exists(Config.LOGO_PATH):
            try:
                img = Image.open(Config.LOGO_PATH)
                fig.add_layout_image(dict(
                    source=img, xref="paper", yref="paper", 
                    x=x_pos, y=y_pos, sizex=0.22, sizey=0.22, 
                    xanchor="center", yanchor="top", opacity=1
                ))
            except: pass

    @staticmethod
    def _add_dynamic_titles_and_axis(fig: go.Figure, title_text: str, x_ticks: list, x_labels: list, num_steps: int = 50, y_max: float = 10.0, y_dtick: float = 1.0):
        loop_sequence = [str(i) for i in range(num_steps)] * 100
        
        fig.update_layout(
            autosize=True,
            title=dict(text=f"<b>{title_text}</b>", x=0.5, xanchor='center', font=Config.TITLE_FONT, y=0.88),
            xaxis=dict(title="<b>NIVELES DE TENSION (kV)</b>", tickmode='array', tickvals=x_ticks, ticktext=x_labels, mirror=True, linecolor='black', showgrid=False, fixedrange=True),
            yaxis=dict(title="<b>Tag(δ) 1·10⁻³</b>", range=[0, y_max], dtick=y_dtick, gridcolor='#E0E0E0', mirror=True, linecolor='black', fixedrange=True),
            yaxis2=dict(range=[0, y_max], dtick=y_dtick, overlaying='y', side='right', showgrid=False, showline=False, tickfont=dict(color="black"), fixedrange=True),
            plot_bgcolor='white', paper_bgcolor='white', height=700, margin=dict(l=80, r=80, t=180, b=180), showlegend=False,
            
            updatemenus=[{
                "buttons": [
                    {"args": [loop_sequence, {"frame": {"duration": 100, "redraw": False}, "fromcurrent": True, "transition": {"duration": 100, "easing": "linear"}}], "label": "▶ PLAY", "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏸ PAUSA", "method": "animate"},
                    {"args": [["0"], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏹ STOP", "method": "animate"}
                ],
                "direction": "left", "pad": {"r": 10, "t": 10}, "showactive": False, "type": "buttons", "x": 0.05, "xanchor": "left", "y": -0.15, "yanchor": "top"
            }]
        )
        if len(x_ticks) > 0:
            fig.add_trace(go.Scatter(x=[x_ticks[0]], y=[0], mode='none', showlegend=False, yaxis='y2', hoverinfo='skip'))

    @staticmethod
    def _generate_sequential_frames_tendencia(v_points, measured_y, base_y, num_frames, trace_indices, show_sweep, full_layout=None):
        m_05, m_10, m_15 = measured_y
        b_05, b_10, b_15 = base_y
        
        frames = []
        for i in range(num_frames):
            p = i / (num_frames - 1)  
            
            curr_05 = b_05 + p * (m_05 - b_05)
            curr_10 = b_10 + p * (m_10 - b_10)
            curr_15 = b_15 + p * (m_15 - b_15)
            
            x_line = [v_points[0], v_points[1], v_points[2]]
            y_line = [curr_05, curr_10, curr_15]

            frame_data = [
                go.Scatter(x=x_line, y=y_line, visible=True),
                go.Scatter(x=x_line, y=y_line, mode='markers+lines', visible=True, cliponaxis=False) 
            ]
            frames.append(go.Frame(data=frame_data, layout=full_layout, name=str(i), traces=trace_indices))
            
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

        steps = np.arange(0.0, 5.5, 0.5) 
        
        for idx, d in enumerate(steps):
            v15_y = u0_measured + d
            v05_y = max(0.0, u0_measured - (5.0 - d))
            
            x_vals = [v_points[0], v_points[1], v_points[2]]
            y_vals = [v05_y, u0_measured, v15_y]
                
            fig.add_trace(go.Scatter(
                x=x_vals, y=y_vals, mode='lines', 
                line=dict(color=color_map.get(d, 'black'), width=1.5), 
                hoverinfo='skip',
                visible=show_fan
            ))

        b_10 = u0_measured
        b_15 = u0_measured + 0.0 
        b_05 = max(0.0, b_10 - 5.0) 
        base_y = [b_05, b_10, b_15]

        fig.add_trace(go.Scatter(
            x=[v_points[0], v_points[1], v_points[2]],
            y=base_y,
            mode='lines',
            line=dict(width=0),
            hoverinfo='skip',
            showlegend=False,
            visible=show_sweep
        ))

        idx_fill = len(fig.data) 
        idx_line = idx_fill + 1 

        x_line_init = [v_points[0], v_points[1], v_points[2]]
        y_line_init = [b_05, b_10, b_15]

        fig.add_trace(go.Scatter(
            x=x_line_init, y=y_line_init, 
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor=Config.COLOR_AREA_FILL, 
            hoverinfo='skip', visible=show_sweep
        ))
        
        fig.add_trace(go.Scatter(
            x=x_line_init, y=y_line_init, 
            mode='lines+markers', 
            line=dict(color=Config.COLOR_MEASURED, width=3),
            marker=dict(size=1, opacity=0), 
            hoverinfo='skip', visible=show_sweep,
            cliponaxis=False 
        ))

        for v in v_points:
            fig.add_vline(x=v, line_width=1.5, line_dash="dash", line_color="#B4C6A6", opacity=0.8)

        labels_u = ['0,5x10⁻³ Uo', '1,0x10⁻³ Uo', '1,5x10⁻³ Uo']
        for i, v in enumerate(v_points):
            x_anchor = "left" if i < 2 else "right"
            x_shift = 10 if i < 2 else -10
            
            fig.add_annotation(
                x=v, y=1.0, xref="x", yref="paper",
                text=f"{labels_u[i]}", showarrow=False, font=dict(size=14, color="#333333"),
                xanchor=x_anchor, xshift=x_shift, yanchor="top", yshift=-10
            )

        u0_disp = f"{u0_measured:.1f}".replace('.', ',')
        
        fig.add_annotation(
            x=v_points[1],    
            y=u0_measured,    
            text=f"ÁREA DE CUMPLIMIENTO PARA 1,0Uo= {u0_disp} x10⁻³",
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
            x=v_points[0], y=u0_measured, text=f"{u0_disp} x10⁻³",
            showarrow=True, arrowhead=0, arrowcolor="#B0B0B0",
            ax=25, ay=-20,
            font=dict(color="#666666", size=10),
            xanchor="left" 
        )
        
        y_max_fan = u0_measured + 5.0
        y_max_disp = f"{y_max_fan:.1f}".replace('.', ',')
        
        fig.add_annotation(
            x=v_points[2], y=y_max_fan, text=f"{y_max_disp} x10⁻³",
            showarrow=True, arrowhead=0, arrowcolor="#B0B0B0",
            ax=-25, ay=-20,
            font=dict(color="#666666", size=10),
            xanchor="right"
        )

        title_text = (
            f"<b>Análisis de Tangente Delta - 0,1Hz - IEEE 400.2</b><br>"
            f"<b>Cable de Media Tensión ({u_nominal}kV)</b><br>"
            f"<b>Variaciones en Función a Tag (δ)x10⁻³Uo</b>"
        )
        
        custom_ticks = list(np.arange(v_points[0], v_points[2] + x_dtick, x_dtick))
        for p in v_points:
            if not any(abs(p - ct) < 0.05 for ct in custom_ticks):
                custom_ticks.append(p)
        custom_ticks = sorted(custom_ticks)
        custom_labels = [f"{v:.1f}".replace('.', ',') for v in custom_ticks]

        ChartBuilder._add_dynamic_titles_and_axis(fig, title_text, custom_ticks, custom_labels, num_frames, y_max, y_dtick)
        
        st_layout = go.Layout(annotations=fig.layout.annotations, shapes=fig.layout.shapes)

        if show_sweep:
            frames = ChartBuilder._generate_sequential_frames_tendencia(
                v_points, measured_y, base_y, num_frames, [idx_fill, idx_line], show_sweep, full_layout=st_layout
            )
            fig.frames = frames
        else:
            fig.frames = []

        fig.update_layout(
            autosize=True,
            separators=",.", 
            title=dict(text=title_text, font=Config.TITLE_FONT, y=0.92),
            xaxis=dict(
                title="<b>Niveles de Tensión <br>(kV)</b>",
                tickmode='array', tickvals=custom_ticks, ticktext=custom_labels,
                range=[v_points[0], v_points[2]], 
                showgrid=False, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickfont=dict(color="#666666"),
                fixedrange=True
            ),
            yaxis=dict(
                title="<b>Tag (δ)<br>1·10⁻³</b>", 
                range=[0, y_max], 
                showgrid=True, gridcolor='#E8E8E8', linecolor='#CCCCCC', mirror=True,
                tickformat=",.1f", tickfont=dict(color="#666666"),
                fixedrange=True
            ),
            yaxis2=dict(
                range=[0, y_max], 
                tickformat=",.1f", tickfont=dict(color="#666666"), linecolor='#CCCCCC',
                fixedrange=True
            ),
            margin=dict(t=120, b=100) 
        )
        ChartBuilder._add_logos(fig, x_pos=0.95, y_pos=-0.10)
        return fig

    @staticmethod
    def get_phasor_geometry(i_r, i_c):
        if i_r > 0.001: 
            angle = np.arctan2(i_c, i_r) 
            theta_delta = np.linspace(angle, np.pi/2, 15)
            r_delta = 0.4
            x_wedge = [0] + list(r_delta * np.cos(theta_delta)) + [0]
            y_wedge = [0] + list(r_delta * np.sin(theta_delta)) + [0]
            
            theta_phi = np.linspace(0, angle, 15)
            r_phi = 0.6
            x_arc = list(r_phi * np.cos(theta_phi))
            y_arc = list(r_phi * np.sin(theta_phi))
            
            delta_label_angle = angle + (np.pi/2 - angle)/2
            x_L_delta = (r_delta + 0.12) * np.cos(delta_label_angle)
            y_L_delta = (r_delta + 0.12) * np.sin(delta_label_angle)
            
            phi_label_angle = angle / 2
            x_L_phi = (r_phi + 0.12) * np.cos(phi_label_angle)
            y_L_phi = (r_phi + 0.12) * np.sin(phi_label_angle)
        else:
            x_wedge, y_wedge, x_arc, y_arc = [np.nan], [np.nan], [np.nan], [np.nan]
            x_L_delta, y_L_delta, x_L_phi, y_L_phi = 0, 0, 0, 0
            
        return x_wedge, y_wedge, x_arc, y_arc, x_L_delta, y_L_delta, x_L_phi, y_L_phi

    @staticmethod
    def draw_area_shifting_demo(v_points, u_nominal, m_y_start, u0_end, ref_delta_pivot, y_max=10.0, y_dtick=1.0, x_dtick=1.0, show_limit_line=False, show_sweep=True):
        num_frames = 50
        u0_start = m_y_start[1] 
        
        fig = make_subplots(
            rows=2, cols=3, 
            column_widths=[0.24, 0.46, 0.30], 
            row_heights=[0.48, 0.52], 
            specs=[
                [{"type": "xy", "rowspan": 1}, {"type": "xy", "rowspan": 2}, {"type": "xy", "rowspan": 2}],
                [{"type": "xy", "rowspan": 1}, None, None]
            ],
            horizontal_spacing=0.06,
            vertical_spacing=0.08
        )
        
        static_shapes = []
        c_x = 0.6 
        offset_y = -0.15 

        static_shapes.extend([
            dict(type="line", x0=c_x, y0=0.85-offset_y, x1=c_x, y1=0.7-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x, y0=0.7-offset_y, x1=c_x+0.3, y1=0.7-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x, y0=0.3-offset_y, x1=c_x+0.3, y1=0.3-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x, y0=0.3-offset_y, x1=c_x, y1=0.15-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x, y0=0.7-offset_y, x1=c_x, y1=0.55-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x, y0=0.45-offset_y, x1=c_x, y1=0.3-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x-0.15, y0=0.55-offset_y, x1=c_x+0.15, y1=0.55-offset_y, xref="x3", yref="y3", line=dict(color="black", width=5)), 
            dict(type="line", x0=c_x-0.15, y0=0.45-offset_y, x1=c_x+0.15, y1=0.45-offset_y, xref="x3", yref="y3", line=dict(color="black", width=5)), 
            dict(type="line", x0=c_x+0.3, y0=0.7-offset_y, x1=c_x+0.3, y1=0.6-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="line", x0=c_x+0.3, y0=0.4-offset_y, x1=c_x+0.3, y1=0.3-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3)), 
            dict(type="rect", x0=c_x+0.2, y0=0.4-offset_y, x1=c_x+0.4, y1=0.6-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3), fillcolor="#D3D3D3"), 
            dict(type="circle", x0=c_x-0.03, y0=0.85-offset_y, x1=c_x+0.03, y1=0.90-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3), fillcolor="white"),
            dict(type="circle", x0=c_x-0.03, y0=0.10-offset_y, x1=c_x+0.03, y1=0.15-offset_y, xref="x3", yref="y3", line=dict(color="black", width=3), fillcolor="white"),
            dict(type="circle", x0=c_x-0.020, y0=0.7-0.015-offset_y, x1=c_x+0.020, y1=0.7+0.015-offset_y, xref="x3", yref="y3", fillcolor="black", line=dict(width=0)),
            dict(type="circle", x0=c_x-0.020, y0=0.3-0.015-offset_y, x1=c_x+0.020, y1=0.3+0.015-offset_y, xref="x3", yref="y3", fillcolor="black", line=dict(width=0)),
        ])

        y_exact_labels = [f"<b>{val:.1f}</b>".replace('.', ',') for val in m_y_start]

        # MODIFICACIÓN: Se ha quitado fill='tozeroy' y fillcolor
        fig.add_trace(go.Scatter(x=v_points, y=m_y_start, mode='lines', line=dict(width=0), hoverinfo='skip', visible=show_sweep, xaxis='x2', yaxis='y2', cliponaxis=False), row=1, col=2) 
        fig.add_trace(go.Scatter(x=v_points, y=m_y_start, mode='lines+markers+text', text=y_exact_labels, textposition="top center", marker=dict(size=12, symbol='diamond', color='white', line=dict(width=2, color='black')), line=dict(color=Config.COLOR_MEASURED, width=3), hoverinfo='skip', visible=show_sweep, xaxis='x2', yaxis='y2', cliponaxis=False), row=1, col=2) 

        final_i_r = 0.85 
        i_c_init = 1.2  
        i_r_init = 0.0 
        
        fig.add_trace(go.Scatter(x=[i_r_init, i_r_init], y=[0, i_c_init], mode='lines', line=dict(color='gray', width=2, dash='dash'), hoverinfo='skip', visible=show_sweep, xaxis='x', yaxis='y'), row=1, col=1) 
        fig.add_trace(go.Scatter(x=[0, i_r_init], y=[i_c_init, i_c_init], mode='lines', line=dict(color='gray', width=2, dash='dash'), hoverinfo='skip', visible=show_sweep, xaxis='x', yaxis='y'), row=1, col=1) 
        
        xw_i, yw_i, xa_i, ya_i, _, _, _, _ = ChartBuilder.get_phasor_geometry(i_r_init, i_c_init)
        fig.add_trace(go.Scatter(x=xw_i, y=yw_i, mode='lines', fill='toself', fillcolor='lightgray', line=dict(width=0), hoverinfo='skip', visible=show_sweep, xaxis='x', yaxis='y'), row=1, col=1) 
        fig.add_trace(go.Scatter(x=xa_i, y=ya_i, mode='lines', line=dict(color='black', width=2), hoverinfo='skip', visible=show_sweep, xaxis='x', yaxis='y'), row=1, col=1) 

        t = np.linspace(0, 2 * np.pi, 200)
        u_wave = np.sin(t)
        angle_rad_init = np.arctan2(i_c_init, i_r_init if i_r_init > 0.0001 else 0.0001)
        i_wave_init = np.sin(t + angle_rad_init)
        
        fig.add_trace(go.Scatter(x=t, y=u_wave, mode='lines', line=dict(color='black', width=2), hoverinfo='skip', name='U'), row=2, col=1) 
        fig.add_trace(go.Scatter(x=t, y=i_wave_init, mode='lines', line=dict(color='#00B050', width=2, dash='dash'), hoverinfo='skip', name='I'), row=2, col=1) 

        base_annotations = []
        base_annotations.append(dict(x=0.5, y=1.15, xref="x domain", yref="y domain", text="<b>Diagrama Fasorial</b>", showarrow=False, font=Config.TITLE_FONT, xanchor="center", yanchor="bottom"))
        base_annotations.append(dict(x=0.5, y=1.15, xref="x4 domain", yref="y4 domain", text="<b>Ondas Senoidales (U e I)</b>", showarrow=False, font=Config.TITLE_FONT, xanchor="center", yanchor="bottom"))
        base_annotations.append(dict(x=0.5, y=1.05, xref="x3 domain", yref="y3 domain", text="<b>Circuito Equivalente</b>", showarrow=False, font=Config.TITLE_FONT, xanchor="center", yanchor="bottom"))

        inequation_text = "<b>[(A + 5) ≥ C ≥ B]</b><br>" "Inecuación segun datos </b><br>" "empíricos IEEE 400.2</B>"
        base_annotations.append(dict(
            x=0.5, y=0.22, xref="x3 domain", yref="y3 domain", 
            text=inequation_text, showarrow=False, 
            font=dict(size=14, color="black", family="Arial"), 
            bgcolor=Config.COLOR_GREY_BOX, borderpad=6,
            xanchor="center", yanchor="top"
        ))

        title_text_main = (
            "<b>Limites Máximos en 0,5x10⁻³Uo, 1,0x10⁻³Uo, 1,5x10⁻³Uo</b><br>"
            "<b>en Función a Tan(δ)x10⁻³Uo</b>"
        )
        base_annotations.append(dict(
            x=0.5, y=1.05, xref="x2 domain", yref="y2 domain", 
            text=title_text_main, showarrow=False, font=Config.TITLE_FONT, 
            xanchor="center", yanchor="bottom", align="center"
        ))

        base_annotations.append(dict(ax=c_x, ay=0.85-offset_y, x=c_x, y=0.78-offset_y, xref="x3", yref="y3", axref="x3", ayref="y3", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="#00B050", text=""))
        base_annotations.append(dict(x=c_x+0.06, y=0.82-offset_y, text="<b>I</b>", showarrow=False, font=dict(size=14, color="#00B050", family="Arial Black"), xref="x3", yref="y3", xanchor="left", yanchor="middle"))
        base_annotations.append(dict(ax=c_x, ay=0.65-offset_y, x=c_x, y=0.58-offset_y, xref="x3", yref="y3", axref="x3", ayref="y3", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="#0055D4", text=""))
        base_annotations.append(dict(x=c_x+0.06, y=0.62-offset_y, text="<b>Ic</b>", showarrow=False, font=dict(size=14, color="#0055D4", family="Arial Black"), xref="x3", yref="y3", xanchor="left", yanchor="middle"))
        base_annotations.append(dict(ax=c_x+0.3, ay=0.70-offset_y, x=c_x+0.3, y=0.60-offset_y, xref="x3", yref="y3", axref="x3", ayref="y3", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="#D50000", text=""))
        base_annotations.append(dict(x=c_x+0.39, y=0.65-offset_y, text="<b>Ir</b>", showarrow=False, font=dict(size=14, color="#D50000", family="Arial Black"), xref="x3", yref="y3", xanchor="left", yanchor="middle"))
        base_annotations.append(dict(x=c_x-0.18, y=0.50-offset_y, text="<b>C</b>", showarrow=False, font=dict(size=20, color="black", family="Arial Black"), xref="x3", yref="y3", xanchor="right", yanchor="middle"))
        base_annotations.append(dict(x=c_x+0.45, y=0.50-offset_y, text="<b>R</b>", showarrow=False, font=dict(size=20, color="black", family="Arial Black"), xref="x3", yref="y3", xanchor="left", yanchor="middle"))
        base_annotations.append(dict(ax=c_x - 0.35, ay=0.7-offset_y, x=c_x - 0.35, y=0.3-offset_y, xref="x3", yref="y3", axref="x3", ayref="y3", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="black", text=""))
        base_annotations.append(dict(x=c_x - 0.35, y=0.25-offset_y, text="<b>U</b>", showarrow=False, font=dict(size=18, color="black", family="Arial Black"), xref="x3", yref="y3", xanchor="center", yanchor="top"))
        base_annotations.append(dict(ax=0, ay=0, x=1.3, y=0, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=4, arrowcolor="black", text=""))
        base_annotations.append(dict(x=1.35, y=0, text="<b>U</b>", showarrow=False, font=dict(size=18, color="black", family="Arial Black"), xref="x", yref="y", xanchor="left", yanchor="middle"))
        base_annotations.append(dict(ax=0, ay=0, x=0, y=1.2, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=4, arrowcolor="#0055D4", text=""))
        base_annotations.append(dict(x=-0.1, y=1.2, text="<b>Ic</b>", showarrow=False, font=dict(size=18, color="#0055D4", family="Arial Black"), xref="x", yref="y", yanchor="bottom", xanchor="right"))
        
        base_annotations.append(dict(
            x=0.31, y=0.68,
            text="Factor de<br>Disipación Tan (δ) = I<sub>R</sub> / I<sub>C</sub>", 
            showarrow=False, 
            font=dict(size=11, color="black", family="Arial Black"), 
            xref="paper", yref="paper", 
            xanchor="right", yanchor="top"
        ))
        
        base_annotations.append(dict(x=np.pi/2, y=1.1, text="<b>U</b>", showarrow=False, font=dict(size=14, color="black", family="Arial Black"), xref="x4", yref="y4", xanchor="center", yanchor="bottom"))

        def get_dynamic_annots(i_r_val, i_c_val, curr_u0_disp, angle_rad=None):
            curr_u0_disp_str = f"{curr_u0_disp:.1f}".replace('.', ',')
            curr_u0_plus_5 = f"{(curr_u0_disp + 5.0):.1f}".replace('.', ',')
            show_ir = i_r_val > 0.001
            safe_ir = i_r_val if i_r_val > 0.0001 else 0.0001
            pos_x_lateral = 0.31 

            annots = [
                dict(x=pos_x_lateral, y=0.93, text=f"<b>A  = 0,5Uo = {curr_u0_disp_str} x10⁻³</b>", showarrow=False, font=dict(size=12, color="white", family="Arial Black"), bgcolor=Config.COLOR_BOX_05, borderpad=6, xref="paper", yref="paper", xanchor="right", yanchor="middle"),
                dict(x=pos_x_lateral, y=0.85, text=f"<b>B  = 1,0Uo = {curr_u0_disp_str} x10⁻³</b>", showarrow=False, font=dict(size=12, color="white", family="Arial Black"), bgcolor=Config.COLOR_BOX_10, borderpad=6, xref="paper", yref="paper", xanchor="right", yanchor="middle"),
                dict(x=pos_x_lateral, y=0.77, text=f"<b>C  = 1,5Uo = {curr_u0_plus_5} x10⁻³</b>", showarrow=False, font=dict(size=12, color="white", family="Arial Black"), bgcolor=Config.COLOR_BOX_15, borderpad=6, xref="paper", yref="paper", xanchor="right", yanchor="middle"),
                dict(ax=0, ay=0, x=safe_ir, y=0, xref="x", yref="y", axref="x", ayref="y", showarrow=show_ir, arrowhead=2 if show_ir else 0, arrowsize=1.2, arrowwidth=3, arrowcolor="#D50000", text=""),
                dict(x=safe_ir, y=0, text="<b>Ir</b>", showarrow=False, font=dict(color="#D50000", size=14, family="Arial Black"), yanchor="top", yshift=-15, xref="x", yref="y"),
                dict(ax=0, ay=0, x=safe_ir, y=i_c_val, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1.2, arrowwidth=3, arrowcolor="#00B050", text=""),
                dict(x=safe_ir, y=i_c_val, text="<b>I</b>", showarrow=False, font=dict(color="#00B050", size=14, family="Arial Black"), xanchor="left", xshift=15, yanchor="bottom", yshift=15, xref="x", yref="y"),
            ]
            
            if angle_rad is not None:
                desfase_x_end = np.pi 
                desfase_x_start = np.pi - angle_rad 
                if abs(desfase_x_end - desfase_x_start) > 0.05:
                    annots.append(dict(x=desfase_x_end, y=0, ax=desfase_x_start, ay=0, xref="x4", yref="y4", axref="x4", ayref="y4", showarrow=True, arrowhead=2, startarrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="black", text=""))
                annots.append(dict(x=(desfase_x_start + desfase_x_end)/2, y=0.1, text="<b>φ</b>", showarrow=False, font=dict(size=20, color="black", family="Arial Black"), xref="x4", yref="y4", xanchor="center", yanchor="bottom"))
                peak_x_i = np.pi/2 - angle_rad
                annots.append(dict(x=peak_x_i, y=1.1, text="<b>I</b>", showarrow=False, font=dict(size=14, color="#00B050", family="Arial Black"), xref="x4", yref="y4", xanchor="center", yanchor="bottom"))
            
            _, _, _, _, xL_d, yL_d, xL_p, yL_p = ChartBuilder.get_phasor_geometry(safe_ir, i_c_val)
            if show_ir:
                annots.append(dict(x=xL_d, y=yL_d, text="<b>δ</b>", showarrow=False, font=dict(size=18, family="Arial", color="black"), xref="x", yref="y", xanchor="center", yanchor="middle"))
                annots.append(dict(x=xL_p, y=yL_p, text="<b>φ</b>", showarrow=False, font=dict(size=16, family="Arial", color="black"), xref="x", yref="y", xanchor="center", yanchor="middle"))
            
            return annots

        frames = []
        for i in range(num_frames):
            progress = i / (num_frames - 1)
            curr_u0 = u0_start + (u0_end - u0_start) * progress
            curr_m_y = [curr_u0, curr_u0, curr_u0 + 5.0]
            curr_m_labels = [f"<b>{val:.1f}</b>".replace('.', ',') for val in curr_m_y]
            i_c = 1.2
            i_r = final_i_r * progress 
            xw, yw, xa, ya, _, _, _, _ = ChartBuilder.get_phasor_geometry(i_r if i_r > 0.0001 else 0.0001, i_c)
            angle_rad = np.arctan2(i_c, i_r if i_r > 0.0001 else 0.0001)
            i_wave = np.sin(t + angle_rad)

            frame_data = [
                go.Scatter(x=v_points, y=curr_m_y), 
                go.Scatter(x=v_points, y=curr_m_y, text=curr_m_labels, cliponaxis=False),
                go.Scatter(x=[0, i_r], y=[i_c, i_c]),
                go.Scatter(x=[i_r, i_r], y=[0, i_c]),
                go.Scatter(x=xw, y=yw),
                go.Scatter(x=xa, y=ya),
                go.Scatter(x=t, y=u_wave),
                go.Scatter(x=t, y=i_wave),
            ]

            curr_u0_val = round(curr_m_y[1], 1)
            f_annots = get_dynamic_annots(i_r, i_c, curr_u0_val, angle_rad)
            frame_layout = go.Layout(annotations=base_annotations + f_annots, shapes=static_shapes)
            frames.append(go.Frame(data=frame_data, layout=frame_layout, name=str(i), traces=[0, 1, 2, 3, 4, 5, 6, 7]))

        if show_sweep: fig.frames = frames
        else: fig.frames = []

        initial_u0_val = round(u0_start, 1)
        init_dyn_annots = get_dynamic_annots(i_r_init, i_c_init, initial_u0_val, angle_rad_init)
        
        loop_sequence_area = [str(i) for i in range(num_frames)] * 100

        custom_ticks_area = list(v_points)
        for t_val in np.arange(v_points[0], v_points[2] + x_dtick, x_dtick):
            if not any(abs(t_val - ct) < 0.05 for ct in custom_ticks_area):
                custom_ticks_area.append(t_val)
        custom_ticks_area = sorted(custom_ticks_area)
        custom_labels_area = [f"{v:.1f}".replace('.', ',') for v in custom_ticks_area]

        fig.update_layout(
            autosize=True,
            annotations=base_annotations + init_dyn_annots,
            shapes=static_shapes,
            separators=",.", 
            xaxis=dict(domain=[0.0, 0.28], range=[-0.30, 1.80], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, constrain="domain"),
            yaxis=dict(domain=[0.45, 0.95], range=[-0.30, 1.50], scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, constrain="domain"),
            xaxis2=dict(domain=[0.35, 0.82], title="<b><br>Niveles de Tensión (kV)</b>", 
                        tickmode='array', tickvals=custom_ticks_area, ticktext=custom_labels_area, 
                        range=[v_points[0], v_points[2]], mirror=True, showline=True, linewidth=1, linecolor='black', showgrid=True, gridcolor='#E8E8E8', fixedrange=True, ticks="outside", ticklen=5, tickwidth=1, tickcolor="black"),
            yaxis2=dict(domain=[0.0, 0.95], title="<b>TG (δ)<br>1·10⁻³</b>", range=[0, y_max], showgrid=True, gridcolor='#E8E8E8', mirror=True, showline=True, linewidth=1, linecolor='black', tickformat=",.1f", tickfont=dict(color="#666666"), fixedrange=True, ticks="outside", ticklen=5, tickwidth=1, tickcolor="black", side="left"),
            xaxis3=dict(domain=[0.85, 1.0], range=[0.0, 1.2], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
            yaxis3=dict(domain=[0.0, 0.95], range=[0.0, 1.0], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
            xaxis4=dict(domain=[0.0, 0.28], range=[0, 2*np.pi], showgrid=True, gridcolor='#E8E8E8', zeroline=True, zerolinecolor='black', showticklabels=False, fixedrange=True),
            yaxis4=dict(domain=[0.0, 0.35], range=[-1.5, 1.5], showgrid=True, gridcolor='#E8E8E8', zeroline=True, zerolinecolor='black', showticklabels=False, fixedrange=True),
            plot_bgcolor='white', paper_bgcolor='white', height=750, margin=dict(l=40, r=60, t=140, b=100), showlegend=False,
            updatemenus=[{
                "buttons": [
                    {"args": [loop_sequence_area, {"frame": {"duration": 100, "redraw": True}, "fromcurrent": True, "transition": {"duration": 100, "easing": "linear"}}], "label": "▶ PLAY", "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏸ PAUSA", "method": "animate"},
                    {"args": [["0"], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}], "label": "⏹ STOP", "method": "animate"}
                ],
                "direction": "left", "pad": {"r": 10, "t": 10}, "showactive": False, "type": "buttons", "x": 0.12, "xanchor": "center", "y": -0.08, "yanchor": "top"
            }]
        )
        ChartBuilder._add_logos(fig, x_pos=0.925, y_pos=-0.02)
        return fig

# ==========================================
# 5. MAIN UI Y AUTOMATIZACIÓN DE CAMPOS
# ==========================================

def main():
    st.markdown(
        """
        <style>
        [data-testid="stSidebarContent"] {
            padding-right: 1rem;
            padding-left: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if os.path.exists(Config.LOGO_PATH):
        try: st.sidebar.image(Image.open(Config.LOGO_PATH), width=220)
        except Exception: st.sidebar.title("INDUCOR")
    else: st.sidebar.title("INDUCOR")

    st.sidebar.header("Parámetros de Ensayo")
    
    modo_seleccionado = st.sidebar.radio(
        "Modo de Visualización",
        ["Tendencia", "Límite máximo para no action"]
    )
    
    u_linea = st.sidebar.number_input("Tensión Nominal (U) [kV]", min_value=0.0, value=33.0, step=0.1)
    v05_def, u0_def, v15_def = calculate_voltages(u_linea)

    with st.sidebar.expander("Ajuste eje X en kV", expanded=False):
        kv_start = st.number_input("Tensión Inicial (0,5x10⁻³Uo)", value=v05_def, format="%.2f")
        kv_mid = st.number_input("Tensión Inicial (1,0x10⁻³Uo)", value=u0_def, format="%.2f")
        kv_end = st.number_input("Tensión Inicial (1,5x10⁻³Uo)", value=v15_def, format="%.2f")
        v_points = [kv_start, kv_mid, kv_end]
        x_dtick = st.number_input("Escala X (Saltos de)", min_value=0.1, value=1.0, step=0.5)

    with st.sidebar.expander("Ajuste eje Y (Tag δ)", expanded=False):
        y_max = st.number_input("Límite Superior Y", min_value=1.0, value=10.0, step=1.0)
        y_dtick = st.number_input("Escala Y (Saltos de)", min_value=0.1, value=1.0, step=0.5)

    if modo_seleccionado == "Tendencia":
        with st.sidebar.expander("Configuración Gráfico Tendencia", expanded=True):
            u0_ref = st.number_input("Pivote del grafico de rectas de tendencia (1,0Uo x10⁻³)", min_value=0.0, max_value=4.0, value=2.0, step=0.1)
            mostrar_abanico = st.checkbox("Mostrar abanico histórico", value=True)
            mostrar_barrido_tend = st.checkbox("Mostrar barrido (área y recta)", value=True, key="chk_barrido_tend")
            
            m_10_val_tendencia = float(u0_ref)
            m_05_calc_tendencia = float(m_10_val_tendencia)
            m_15_calc_tendencia = float(m_10_val_tendencia + 5.0)
            m_y_tendencia = [m_05_calc_tendencia, m_10_val_tendencia, m_15_calc_tendencia]

    elif modo_seleccionado == "Límite máximo para no action":
        with st.sidebar.expander("Configuración limite máximo para no action", expanded=True):
            p_delta_pivot = 1.5 
            mostrar_barrido_noact = st.checkbox("Mostrar barrido (Recta roja)", value=True, key="chk_barrido_noact")
            
            demo_u0_end_noaction = st.number_input("1,0Uo final (x10⁻³)", key="end_noaction", step=0.1, value=4.0, max_value=4.0)
            m_10_val_noaction = st.number_input("1,0Uo inicial (x10⁻³)", min_value=0.0, max_value=20.0, key='m_10_noaction', step=0.1, on_change=sync_mediciones_noaction)

            m_y_start_anim = [float(m_10_val_noaction), float(m_10_val_noaction), float(m_10_val_noaction) + 5.0]
            u0_end_anim = float(demo_u0_end_noaction)

    if u_linea > 0:
        if modo_seleccionado == "Tendencia":
            st.subheader("Análisis de Tendencia")
            col1, col2, col3 = st.columns([0.1, 5, 0.1])
            with col2:
                fig_fan = ChartBuilder.draw_fan_animated(v_points, u0_ref, u_linea, m_y_tendencia, y_max=y_max, y_dtick=y_dtick, x_dtick=x_dtick, show_fan=mostrar_abanico, show_sweep=mostrar_barrido_tend)
                
                st.plotly_chart(fig_fan, use_container_width=True, config={'displayModeBar': False}, key="tend_fan")

                if st.button("Generar y Descargar GIF (Tendencia)"):
                    with st.spinner("Procesando GIF de Tendencia..."):
                        try:
                            gif_bytes = generate_gif_from_frames(fig_fan, fig_fan.frames)
                            st.download_button(label="Descargar GIF", data=gif_bytes, file_name="tendencia.gif", mime="image/gif")
                        except Exception as e: st.error(f"Error: {e}")
            
        elif modo_seleccionado == "Límite máximo para no action":
            st.subheader("Límite Máximo para No Action")
            st.markdown("<br>", unsafe_allow_html=True) 
            fig_area = ChartBuilder.draw_area_shifting_demo(v_points, u_linea, m_y_start_anim, u0_end_anim, p_delta_pivot, y_max=y_max, y_dtick=y_dtick, x_dtick=x_dtick, show_sweep=mostrar_barrido_noact)
            st.plotly_chart(fig_area, use_container_width=True, config={'displayModeBar': False, 'staticPlot': False}, key="area_noaction")

            if st.button("Generar y Descargar GIF (Limite máximo para no action)"):
                with st.spinner("Procesando GIF..."):
                    try:
                        gif_bytes = generate_gif_from_frames(fig_area, fig_area.frames)
                        st.download_button(label="Descargar GIF", data=gif_bytes, file_name="dinamica.gif", mime="image/gif")
                    except Exception as e: st.error(f"Error: {e}")
                        
    else:
        st.warning("Ingrese una Tensión Nominal válida para comenzar.")

if __name__ == "__main__":
    main()