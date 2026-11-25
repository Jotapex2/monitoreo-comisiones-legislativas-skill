"""
generate_commission_docs.py
Generador Profesional de Documentos Word (.docx) para Comisiones Legislativas.
Produce:
1. Minuta Ejecutiva: Formato de alto impacto (~2.5 pags), paleta navy institucional (#1A365D), recuadros destacados para lectura de secretaría y viñetas estructuradas.
2. Informe de Comisión: Formato legislativo institucional estándar del Congreso Nacional (Senado y Cámara), con Orden del día, Asistentes por partido, Exposiciones, Debate e Indicaciones.
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

COLOR_PRIMARY = RGBColor(26, 54, 93)     # #1A365D Deep Navy
COLOR_SECONDARY = RGBColor(43, 108, 176) # #2B6CB0 Blue
COLOR_DARK = RGBColor(45, 55, 72)        # #2D3748 Charcoal Body

def apply_page_margins(doc):
    for sec in doc.sections:
        sec.top_margin = Inches(1)
        sec.bottom_margin = Inches(1)
        sec.left_margin = Inches(1)
        sec.right_margin = Inches(1)

def set_callout_border(cell, border_color='2B6CB0', fill_color='F7FAFC'):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(tcBorders)
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_color}"/>')
    tcPr.append(shd)

def create_minuta_document(data, output_path):
    """
    Crea la Minuta Ejecutiva en Word (.docx) a partir de un diccionario estructurado.
    """
    doc = docx.Document()
    apply_page_margins(doc)
    
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(10.5)
    style_normal.font.color.rgb = COLOR_DARK
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(4)
    
    # Titulo principal
    p_title = doc.add_paragraph()
    r_title = p_title.add_run("INFORME Y RESUMEN EJECUTIVO DE LA SESIÓN\n")
    r_title.font.size = Pt(17)
    r_title.font.bold = True
    r_title.font.color.rgb = COLOR_PRIMARY
    
    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run(f"{data.get('comision', '')}\n{data.get('camara', '')}")
    r_sub.font.size = Pt(11)
    r_sub.font.bold = True
    r_sub.font.color.rgb = COLOR_SECONDARY
    
    # Tabla de metadata (soporta lista 'metadatos' ampliada o campos clasicos fecha/materia)
    meta = data.get('metadatos') or [
        ("Fecha:", data.get('fecha', '')),
        ("Materia:", data.get('materia', '')),
    ]
    table = doc.add_table(rows=len(meta), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row in table.rows:
        row.cells[0].width = Inches(1.8)
        row.cells[1].width = Inches(4.7)
    for idx, (label, val) in enumerate(meta):
        c1, c2 = table.cell(idx, 0), table.cell(idx, 1)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(label)
        r1.font.bold = True
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = COLOR_PRIMARY
        
        p2 = c2.paragraphs[0]
        r2 = p2.add_run(val)
        r2.font.size = Pt(9.5)
        
        for c in (c1, c2):
            tcPr = c._tc.get_or_add_tcPr()
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F4F8"/>')
            tcPr.append(shd)
            borders = parse_xml(f'''
                <w:tcBorders {nsdecls("w")}>
                    <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>
                    <w:left w:val="none"/>
                    <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>
                    <w:right w:val="none"/>
                </w:tcBorders>
            ''')
            tcPr.append(borders)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    
    # Secciones
    for sec in data.get('secciones', []):
        p_sec = doc.add_paragraph()
        p_sec.paragraph_format.space_before = Pt(14)
        p_sec.paragraph_format.space_after = Pt(4)
        p_sec.paragraph_format.keep_with_next = True
        r_sec = p_sec.add_run(sec['titulo'])
        r_sec.font.size = Pt(13)
        r_sec.font.bold = True
        r_sec.font.color.rgb = COLOR_PRIMARY
        
        # Subrayado sutil
        pPr = p_sec._p.get_or_add_pPr()
        pBdr = parse_xml(f'''
            <w:pBdr {nsdecls("w")}>
                <w:bottom w:val="single" w:sz="12" w:space="4" w:color="1A365D"/>
            </w:pBdr>
        ''')
        pPr.append(pBdr)
        
        for elem in sec.get('elementos', []):
            if elem['tipo'] == 'parrafo':
                doc.add_paragraph(elem['texto'])
            elif elem['tipo'] == 'subtitulo':
                p_sub2 = doc.add_paragraph()
                p_sub2.paragraph_format.space_before = Pt(10)
                p_sub2.paragraph_format.space_after = Pt(3)
                p_sub2.paragraph_format.keep_with_next = True
                r_s2 = p_sub2.add_run(elem['texto'])
                r_s2.font.size = Pt(11)
                r_s2.font.bold = True
                r_s2.font.color.rgb = COLOR_SECONDARY
            elif elem['tipo'] == 'bullet':
                p_b = doc.add_paragraph(style='List Bullet')
                p_b.paragraph_format.space_after = Pt(3)
                p_b.paragraph_format.line_spacing = 1.15
                if 'prefijo' in elem:
                    r_pre = p_b.add_run(elem['prefijo'])
                    r_pre.font.bold = True
                    r_pre.font.color.rgb = COLOR_PRIMARY
                p_b.add_run(elem['texto'])
            elif elem['tipo'] == 'quote_box':
                tbl = doc.add_table(rows=1, cols=1)
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                cell = tbl.cell(0, 0)
                cell.width = Inches(6.5)
                set_callout_border(cell, '2B6CB0', 'F7FAFC')
                p_box = cell.paragraphs[0]
                p_box.paragraph_format.space_before = Pt(3)
                p_box.paragraph_format.space_after = Pt(2)
                p_box.paragraph_format.line_spacing = 1.15
                if 'titulo' in elem:
                    r_bt = p_box.add_run(elem['titulo'] + '\n')
                    r_bt.font.bold = True
                    r_bt.font.size = Pt(9.5)
                    r_bt.font.color.rgb = COLOR_PRIMARY
                r_bc = p_box.add_run(elem['texto'])
                r_bc.font.italic = True
                r_bc.font.size = Pt(9.5)
                r_bc.font.color.rgb = COLOR_DARK
                doc.add_paragraph().paragraph_format.space_after = Pt(2)
            elif elem['tipo'] == 'tabla':
                headers = elem.get('encabezados', [])
                rows = elem.get('filas', [])
                if headers or rows:
                    ncols = len(headers) if headers else len(rows[0])
                    total_rows = (1 if headers else 0) + len(rows)
                    tbl = doc.add_table(rows=total_rows, cols=ncols)
                    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                    row_offset = 0
                    if headers:
                        for c_idx, h_text in enumerate(headers):
                            cell = tbl.cell(0, c_idx)
                            p_h = cell.paragraphs[0]
                            r_h = p_h.add_run(str(h_text))
                            r_h.font.bold = True
                            r_h.font.size = Pt(9.5)
                            r_h.font.color.rgb = RGBColor(255, 255, 255)
                            tcPr = cell._tc.get_or_add_tcPr()
                            tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="1A365D"/>'))
                        row_offset = 1
                    for r_idx, r_vals in enumerate(rows):
                        fill = "F7FAFC" if r_idx % 2 == 1 else "FFFFFF"
                        for c_idx, val in enumerate(r_vals):
                            cell = tbl.cell(row_offset + r_idx, c_idx)
                            p_c = cell.paragraphs[0]
                            r_c = p_c.add_run(str(val))
                            r_c.font.size = Pt(9.5)
                            r_c.font.color.rgb = COLOR_DARK
                            tcPr = cell._tc.get_or_add_tcPr()
                            tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>'))
                            tcPr.append(parse_xml(f'''
                                <w:tcBorders {nsdecls("w")}>
                                    <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>
                                    <w:left w:val="none"/>
                                    <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>
                                    <w:right w:val="none"/>
                                </w:tcBorders>
                            '''))
                    doc.add_paragraph().paragraph_format.space_after = Pt(3)
                
    doc.save(output_path)
    print(f"[OK] Minuta guardada en: {output_path}")

def create_informe_document(data, output_path):
    """
    Crea el Informe de Comisión institucional en Word (.docx) acorde al estándar del Congreso.
    """
    doc = docx.Document()
    apply_page_margins(doc)
    
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Arial'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(4)
    
    # 1. Encabezado institucional
    p_com = doc.add_paragraph()
    p_com.paragraph_format.space_before = Pt(0)
    p_com.paragraph_format.space_after = Pt(2)
    r_com = p_com.add_run(data.get('comision', 'Comisión'))
    r_com.font.bold = True
    r_com.font.size = Pt(14)
    
    p_cam = doc.add_paragraph()
    p_cam.paragraph_format.space_after = Pt(2)
    r_cam = p_cam.add_run(data.get('camara', 'Congreso Nacional'))
    r_cam.font.bold = True
    r_cam.font.size = Pt(14)
    
    p_fec = doc.add_paragraph(data.get('fecha', ''))
    p_fec.paragraph_format.space_after = Pt(12)
    
    # 2. Orden del día
    p_ord = doc.add_paragraph()
    r_ord = p_ord.add_run("Orden del día")
    r_ord.font.bold = True
    for item in data.get('orden_del_dia', []):
        p_item = doc.add_paragraph(style='List Bullet')
        p_item.paragraph_format.space_after = Pt(3)
        p_item.add_run(item)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    
    # 3. Asistentes
    p_asis = doc.add_paragraph()
    r_asis = p_asis.add_run("Asistentes:")
    r_asis.font.bold = True
    for asistente in data.get('asistentes', []):
        p_a = doc.add_paragraph(style='List Bullet')
        p_a.paragraph_format.space_after = Pt(2)
        p_a.add_run(asistente)
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # 4. Puntos en Tabla / Secciones
    for punto in data.get('puntos_tabla', []):
        if 'titulo' in punto:
            p_pt = doc.add_paragraph()
            p_pt.paragraph_format.space_before = Pt(12)
            p_pt.paragraph_format.space_after = Pt(4)
            p_pt.paragraph_format.keep_with_next = True
            r_pt = p_pt.add_run(punto['titulo'])
            r_pt.font.bold = True
            r_pt.font.size = Pt(12)
            
        # Exposiciones
        if 'exposiciones' in punto and punto['exposiciones']:
            p_exp_h = doc.add_paragraph()
            p_exp_h.paragraph_format.space_before = Pt(8)
            p_exp_h.paragraph_format.space_after = Pt(3)
            r_exp_h = p_exp_h.add_run("Exposiciones")
            r_exp_h.font.bold = True
            
            for exp in punto['exposiciones']:
                p_exp_name = doc.add_paragraph()
                p_exp_name.paragraph_format.space_before = Pt(4)
                p_exp_name.paragraph_format.space_after = Pt(2)
                r_en = p_exp_name.add_run(exp['orador'])
                r_en.font.bold = True
                for par in exp.get('parrafos', []):
                    p_p = doc.add_paragraph(par)
                    p_p.paragraph_format.space_after = Pt(4)
                    
        # Debate
        if 'debate' in punto and punto['debate']:
            p_deb_h = doc.add_paragraph()
            p_deb_h.paragraph_format.space_before = Pt(8)
            p_deb_h.paragraph_format.space_after = Pt(3)
            r_deb_h = p_deb_h.add_run("Debate")
            r_deb_h.font.bold = True
            
            for d in punto['debate']:
                if 'orador' in d:
                    p_d_name = doc.add_paragraph()
                    p_d_name.paragraph_format.space_before = Pt(5)
                    p_d_name.paragraph_format.space_after = Pt(2)
                    r_dn = p_d_name.add_run(d['orador'])
                    r_dn.font.bold = True
                if 'texto' in d:
                    p_dt = doc.add_paragraph(d['texto'])
                    p_dt.paragraph_format.space_after = Pt(4)
                if 'votacion' in d:
                    p_v = doc.add_paragraph()
                    p_v.paragraph_format.space_before = Pt(4)
                    p_v.paragraph_format.space_after = Pt(4)
                    r_v = p_v.add_run(d['votacion'])
                    r_v.font.bold = True
                    
    # 5. Cierre o despacho
    if 'cierre' in data:
        p_cierre = doc.add_paragraph()
        p_cierre.paragraph_format.space_before = Pt(14)
        r_cierre = p_cierre.add_run(data['cierre'])
        r_cierre.font.bold = True
        
    doc.save(output_path)
    print(f"[OK] Informe institucional guardado en: {output_path}")
