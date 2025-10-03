import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse
import io
from io import BytesIO
import tempfile
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EstadisticasConsultasView(APIView):
    def get(self, request):
        try:
            # URLs de los servicios - USANDO CONFIGURACIÓN DE SETTINGS
            API_CONSULTAS = settings.API_CONSULTAS
            API_PROFESIONALES = settings.API_PROFESIONALES
            API_ATLETAS = settings.API_ATLETAS
            
            # 1. Obtener todas las consultas
            logger.info(f"Consultando consultas en: {API_CONSULTAS}")
            consultas_response = requests.get(API_CONSULTAS, timeout=10)
            consultas_response.raise_for_status()
            todas_consultas = consultas_response.json()
            
            # 2. Filtrar consultas del mes actual
            mes_actual = datetime.now().month
            año_actual = datetime.now().year
            
            # 3. Calcular estadísticas básicas
            consultas_mes_actual = [
                c for c in todas_consultas 
                if datetime.strptime(c['fecha'], '%Y-%m-%d').month == mes_actual
                and datetime.strptime(c['fecha'], '%Y-%m-%d').year == año_actual
            ]
            
            total_consultas = len(consultas_mes_actual)
            
            # 4. Obtener todos los profesionales
            profesionales_response = requests.get(API_PROFESIONALES, timeout=10)
            profesionales_response.raise_for_status()
            todos_profesionales = profesionales_response.json()
            
            # 5. Obtener todos los atletas
            atletas_response = requests.get(API_ATLETAS, timeout=10)
            atletas_response.raise_for_status()
            todos_atletas = atletas_response.json()
            
            # 6. Datos mensuales por profesional (últimos 12 meses)
            monthly_data_by_profesional = []
            meses_mostrar = 12
            
            for i in range(meses_mostrar):
                mes_offset = meses_mostrar - i - 1
                month = (mes_actual - mes_offset - 1) % 12 + 1
                year = año_actual - (1 if mes_actual - mes_offset - 1 < 0 else 0)
                
                consultas_mes = [
                    c for c in todas_consultas 
                    if datetime.strptime(c['fecha'], '%Y-%m-%d').month == month
                    and datetime.strptime(c['fecha'], '%Y-%m-%d').year == year
                ]
                
                profesionales_data_mes = []
                for profesional in todos_profesionales:
                    profesional_id = str(profesional['id'])
                    count = sum(1 for c in consultas_mes 
                              if str(c.get('profesional_salud', c.get('profesional_salud_id', ''))) == profesional_id)
                    
                    nombre_completo = f"{profesional.get('nombre', '')} {profesional.get('apPaterno', '')}".strip()
                    
                    profesionales_data_mes.append({
                        'profesional_id': profesional['id'],
                        'profesional_name': nombre_completo,
                        'count': count
                    })
                
                monthly_data_by_profesional.append({
                    'mes': datetime(year, month, 1).strftime('%b'),
                    'mes_numero': month,
                    'ano': year,
                    'profesionales': profesionales_data_mes,
                    'total': len(consultas_mes)
                })
            
            # 7. Datos totales por profesional
            profesionales_data = []
            for profesional in todos_profesionales:
                profesional_id = str(profesional['id'])
                total_consultas_prof = sum(
                    1 for c in consultas_mes_actual 
                    if str(c.get('profesional_salud', c.get('profesional_salud_id', ''))) == profesional_id
                )
                
                nombre_completo = f"{profesional.get('nombre', '')} {profesional.get('apPaterno', '')}".strip()
                
                profesionales_data.append({
                    'nombre': nombre_completo,
                    'id': profesional_id,
                    'total': total_consultas_prof,
                    'especialidad': profesional.get('especialidad', 'Sin especialidad')
                })
            
            # 8. Datos por atleta (top 10 con más consultas)
            atletas_data = []
            for atleta in todos_atletas:
                atleta_id = str(atleta['id'])
                total_consultas_atleta = sum(
                    1 for c in todas_consultas 
                    if str(c.get('atleta', c.get('atleta_id', ''))) == atleta_id
                )
                
                nombre_completo = f"{atleta.get('nombre', '')} {atleta.get('apPaterno', '')}".strip()
                
                if total_consultas_atleta > 0:
                    atletas_data.append({
                        'nombre': nombre_completo,
                        'id': atleta_id,
                        'total': total_consultas_atleta
                    })
            
            top_atletas = sorted(atletas_data, key=lambda x: x['total'], reverse=True)[:10]
            
            # 9. Distribución por diagnóstico común
            diagnosticos = {}
            for consulta in todas_consultas:
                diagnostico = consulta.get('diagnostico', 'Sin diagnóstico').strip()
                if diagnostico and diagnostico != 'Sin diagnóstico':
                    diagnosticos[diagnostico] = diagnosticos.get(diagnostico, 0) + 1
            
            top_diagnosticos = sorted(
                [{'nombre': k, 'total': v} for k, v in diagnosticos.items()], 
                key=lambda x: x['total'], 
                reverse=True
            )[:5]
            
            logger.info(f"Total consultas procesadas: {len(todas_consultas)}")
            logger.info(f"Profesionales encontrados: {len(todos_profesionales)}")
            logger.info(f"Atletas encontrados: {len(todos_atletas)}")
            
            return Response({
                'total_consultas': len(todas_consultas),
                'consultas_mes_actual': len(consultas_mes_actual),
                'profesionales_data': profesionales_data,
                'monthly_data_by_profesional': monthly_data_by_profesional,
                'monthly_data': [{'mes': m['mes'], 'total': m['total']} for m in monthly_data_by_profesional],
                'top_atletas': top_atletas,
                'top_diagnosticos': top_diagnosticos
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión: {str(e)}")
            return Response({
                'error': 'Error al conectar con los servicios externos',
                'detalles': str(e)
            }, status=503)
            
        except Exception as e:
            logger.exception("Error interno del servidor")
            return Response({
                'error': 'Error interno del servidor',
                'detalles': str(e)
            }, status=500)


class GenerarReporteConsultasPDFView(APIView):
    """
    Vista que genera reportes PDF de consultas médicas con filtros aplicables.
    """

    # Configuración de endpoints - USANDO SETTINGS
    @property
    def CONSULTAS_API_URL(self):
        return settings.API_CONSULTAS
    
    @property
    def CATALOGOS_API_BASE_URL(self):
        # Extraer la base de la URL de API_ATLETAS
        return settings.API_BASE_URL + '/Catalogos/'
    
    TIMEOUT = 10  # segundos

    def post(self, request):
        """
        Genera un reporte PDF de consultas médicas con filtros aplicables.
        """
        try:
            logger.info("Iniciando generación de reporte PDF con filtros: %s", request.data)
            
            # 1. Validación de parámetros requeridos
            if not all(k in request.data for k in ['fecha_inicio', 'fecha_fin']):
                error_msg = "Las fechas de inicio y fin son requeridas"
                logger.error(error_msg)
                return Response(
                    {'error': error_msg}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Obtener todas las consultas del servicio externo
            try:
                params = {
                    'fecha_inicio': request.data.get('fecha_inicio'),
                    'fecha_fin': request.data.get('fecha_fin')
                }
                
                if request.data.get('atleta_id'):
                    params['atleta_id'] = request.data.get('atleta_id')
                    
                if request.data.get('profesional_id'):
                    params['profesional_id'] = request.data.get('profesional_id')
                
                logger.info("Solicitando consultas con parámetros: %s", params)
                response = requests.get(
                    self.CONSULTAS_API_URL,
                    params=params,
                    timeout=self.TIMEOUT
                )
                response.raise_for_status()
                todas_consultas = response.json()
                logger.info("Total de consultas obtenidas del servicio: %d", len(todas_consultas))
            except requests.exceptions.RequestException as e:
                logger.error("Error al obtener consultas: %s", str(e))
                return Response(
                    {'error': 'No se pudieron obtener las consultas del servicio: ' + str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # 3. Obtener catálogos necesarios
            catalogos = self._obtener_catalogos()
            if isinstance(catalogos, Response):
                return catalogos

            # 4. Filtrar consultas según parámetros
            consultas_filtradas = self._filtrar_consultas(
                todas_consultas, 
                request.data,
                catalogos
            )
            logger.info("Consultas después de filtrar: %d", len(consultas_filtradas))

            # 5. Enriquecer consultas con datos completos
            consultas_enriquecidas = self._enriquecer_consultas(
                consultas_filtradas,
                catalogos
            )

            # 6. Generar PDF
            pdf_buffer = self._generar_pdf(
                consultas_enriquecidas,
                request.data
            )

            # 7. Preparar respuesta
            fecha_inicio = request.data['fecha_inicio']
            fecha_fin = request.data['fecha_fin']
            response = HttpResponse(
                pdf_buffer.getvalue(), 
                content_type='application/pdf'
            )
            filename = f"reporte_consultas_{fecha_inicio}_{fecha_fin}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            
            logger.info("Reporte PDF generado exitosamente")
            return response
            
        except Exception as e:
            logger.error("Error inesperado al generar reporte: %s", str(e), exc_info=True)
            return Response(
                {
                    'error': 'Error interno al generar el reporte',
                    'detalles': str(e)
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    def options(self, request):
        """
        Maneja las solicitudes OPTIONS para CORS preflight
        """
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    def _obtener_catalogos(self):
        """
        Obtiene todos los catálogos necesarios desde los servicios externos.
        """
        catalogos = {
            'atletas': {},
            'profesionales': {}
        }
        
        try:
            # Obtener atletas - USANDO SETTINGS
            response = requests.get(
                settings.API_ATLETAS,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            for atleta in response.json():
                catalogos['atletas'][str(atleta['id'])] = atleta
            
            # Obtener profesionales - USANDO SETTINGS
            response = requests.get(
                settings.API_PROFESIONALES,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            for profesional in response.json():
                catalogos['profesionales'][str(profesional['id'])] = profesional
                
            return catalogos
            
        except requests.exceptions.RequestException as e:
            logger.error("Error al obtener catálogos: %s", str(e))
            return Response(
                {
                    'error': 'No se pudieron obtener los catálogos necesarios',
                    'detalles': str(e)
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    def _filtrar_consultas(self, consultas, filtros, catalogos):
        """
        Filtra las consultas según los parámetros recibidos.
        """
        try:
            fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d')
            fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').replace(
                hour=23, minute=59, second=59
            )
        except ValueError as e:
            logger.error("Error al parsear fechas: %s", str(e))
            return consultas
        
        consultas_filtradas = []
        
        for consulta in consultas:
            try:
                # 1. Filtrar por fecha
                fecha_consulta = None
                fecha_campos = ['fecha', 'creado_el', 'fecha_consulta', 'created_at']
                
                for campo in fecha_campos:
                    if campo in consulta and consulta[campo]:
                        try:
                            for formato in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                                try:
                                    fecha_consulta = datetime.strptime(consulta[campo], formato)
                                    break
                                except ValueError:
                                    continue
                            if fecha_consulta:
                                break
                        except Exception:
                            continue
                
                if not fecha_consulta:
                    logger.warning("No se pudo determinar la fecha para consulta %s", consulta.get('id', 'desconocido'))
                    consultas_filtradas.append(consulta)
                    continue
                
                if not (fecha_inicio <= fecha_consulta <= fecha_fin):
                    continue
                
                # 2. Filtrar por atleta
                if 'atleta_id' in filtros and filtros['atleta_id'] not in [None, "todos", ""]:
                    atleta_id_consulta = self._obtener_id_de_campo(consulta, ['atleta_id', 'atleta', 'id_atleta', 'paciente_id', 'paciente'])
                    
                    if not atleta_id_consulta or str(atleta_id_consulta) != str(filtros['atleta_id']):
                        continue
                
                # 3. Filtrar por profesional
                if 'profesional_id' in filtros and filtros['profesional_id'] not in [None, "todos", ""]:
                    profesional_id_consulta = self._obtener_id_de_campo(consulta, ['profesional_salud_id', 'profesional_salud', 'profesional_id', 'profesional', 'id_profesional', 'medico_id', 'medico'])
                    
                    if not profesional_id_consulta or str(profesional_id_consulta) != str(filtros['profesional_id']):
                        continue
                
                consultas_filtradas.append(consulta)
                
            except Exception as e:
                logger.warning("Error al procesar consulta %s: %s", consulta.get('id', 'desconocido'), str(e))
                consultas_filtradas.append(consulta)
                continue
                
        return consultas_filtradas

    def _enriquecer_consultas(self, consultas, catalogos):
        """
        Enriquece las consultas con información de catálogos.
        """
        consultas_enriquecidas = []
        
        for consulta in consultas:
            diagnostico = "No especificado"
            for campo in ['diagnostico', 'diagnóstico', 'diagnostic']:
                if campo in consulta and consulta[campo]:
                    diagnostico = consulta[campo]
                    break
            
            tratamiento = "No especificado"
            for campo in ['tratamiento', 'treatment']:
                if campo in consulta and consulta[campo]:
                    tratamiento = consulta[campo]
                    break
                    
            consulta_enriquecida = {
                'id': consulta.get('id', 'N/A'),
                'fecha': self._formatear_fecha(self._obtener_fecha_consulta(consulta)),
                'diagnostico': diagnostico,
                'tratamiento': tratamiento
            }
            
            # Agregar información del atleta
            atleta_id = self._obtener_id_de_campo(consulta, ['atleta_id', 'atleta', 'id_atleta', 'paciente_id', 'paciente'])
            if atleta_id and str(atleta_id) in catalogos['atletas']:
                atleta = catalogos['atletas'][str(atleta_id)]
                consulta_enriquecida['atleta_id'] = atleta_id
                consulta_enriquecida['atleta_nombre'] = f"{atleta.get('nombre', '')} {atleta.get('apPaterno', '')} {atleta.get('apMaterno', '')}".strip()
            else:
                consulta_enriquecida['atleta_id'] = atleta_id
                consulta_enriquecida['atleta_nombre'] = 'Atleta desconocido'
                
            # Agregar información del profesional
            profesional_id = self._obtener_id_de_campo(consulta, ['profesional_salud_id', 'profesional_salud', 'profesional_id', 'profesional', 'id_profesional', 'medico_id', 'medico'])
            if profesional_id and str(profesional_id) in catalogos['profesionales']:
                profesional = catalogos['profesionales'][str(profesional_id)]
                consulta_enriquecida['profesional_id'] = profesional_id
                consulta_enriquecida['profesional_nombre'] = f"{profesional.get('nombre', '')} {profesional.get('apPaterno', '')} {profesional.get('apMaterno', '')}".strip()
            else:
                consulta_enriquecida['profesional_id'] = profesional_id
                consulta_enriquecida['profesional_nombre'] = 'Profesional desconocido'
                
            consultas_enriquecidas.append(consulta_enriquecida)
            
        return consultas_enriquecidas
    
    def _obtener_fecha_consulta(self, consulta):
        """
        Obtiene la fecha de consulta de diferentes campos posibles.
        """
        fecha_campos = ['fecha', 'creado_el', 'fecha_consulta', 'created_at']
        for campo in fecha_campos:
            if campo in consulta and consulta[campo]:
                return consulta[campo]
        return ""
        
    def _obtener_id_de_campo(self, objeto, posibles_campos):
        """
        Obtiene el ID de un campo que puede estar en diferentes formatos.
        """
        for campo in posibles_campos:
            if campo in objeto:
                valor = objeto[campo]
                if isinstance(valor, dict) and 'id' in valor:
                    return str(valor['id'])
                elif valor is not None:
                    return str(valor)
        return None

    def _formatear_fecha(self, fecha_str):
        """
        Formatea una fecha ISO a un formato más legible.
        """
        if not fecha_str:
            return "Fecha no disponible"
            
        try:
            for formato in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    fecha = datetime.strptime(fecha_str, formato)
                    return fecha.strftime('%d/%m/%Y %H:%M')
                except ValueError:
                    continue
            return fecha_str
        except Exception:
            return fecha_str

    def _generar_pdf(self, consultas, filtros):
        """
        Genera un PDF con la información de las consultas.
        """
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        subtitle_style = styles['Heading2']
        normal_style = styles['Normal']
        small_style = ParagraphStyle(
            'Small',
            parent=styles['BodyText'],
            fontSize=8,
            textColor=colors.grey
        )
        
        elements = []
        
        # Encabezado
        elements.append(Paragraph("Reporte de Consultas Médicas", title_style))
        elements.append(Paragraph(
            f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
            small_style
        ))
        elements.append(Spacer(1, 0.25*inch))
        
        # Filtros aplicados
        elements.append(Paragraph("Filtros Aplicados:", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').strftime('%d/%m/%Y')
        fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').strftime('%d/%m/%Y')
        elements.append(Paragraph(f"Período: {fecha_inicio} - {fecha_fin}", normal_style))
        
        if 'atleta_id' in filtros and filtros['atleta_id'] not in [None, "todos", ""]:
            for consulta in consultas:
                if str(consulta.get('atleta_id')) == str(filtros['atleta_id']):
                    elements.append(Paragraph(
                        f"Atleta: {consulta['atleta_nombre']}", 
                        normal_style
                    ))
                    break
        
        if 'profesional_id' in filtros and filtros['profesional_id'] not in [None, "todos", ""]:
            for consulta in consultas:
                if str(consulta.get('profesional_id')) == str(filtros['profesional_id']):
                    elements.append(Paragraph(
                        f"Profesional: {consulta['profesional_nombre']}", 
                        normal_style
                    ))
                    break
        
        elements.append(Spacer(1, 0.25*inch))
        
        # Estadísticas
        elements.append(Paragraph("Resumen Estadístico:", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        total = len(consultas)
        
        profesionales = {}
        for consulta in consultas:
            profesional = consulta['profesional_nombre']
            if profesional in profesionales:
                profesionales[profesional] += 1
            else:
                profesionales[profesional] = 1
        
        stats_data = [
            ["Total de Consultas", "Consultas por Profesional"],
            [
                str(total),
                "\n".join([f"{k}: {v}" for k, v in profesionales.items()])
            ]
        ]
        
        stats_table = Table(
            stats_data, 
            colWidths=[2.5*inch, 4.5*inch]
        )
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, 1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#EFF6FF')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BFDBFE')),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # Detalle de consultas
        if consultas:
            elements.append(Paragraph("Detalle de Consultas:", subtitle_style))
            elements.append(Spacer(1, 0.1*inch))
            
            detail_headers = [
                "Fecha", 
                "Atleta", 
                "Profesional", 
                "Diagnóstico", 
                "Tratamiento"
            ]
            
            detail_data = [detail_headers]
            
            for consulta in consultas:
                detail_data.append([
                    consulta.get('fecha', 'No especificada'),
                    consulta.get('atleta_nombre', 'No especificado'),
                    consulta.get('profesional_nombre', 'No especificado'),
                    Paragraph(consulta.get('diagnostico', 'No especificado'), styles['Normal']),
                    Paragraph(consulta.get('tratamiento', 'No especificado'), styles['Normal'])
                ])
            
            detail_table = Table(
                detail_data, 
                colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 2.0*inch, 2.0*inch],
                repeatRows=1
            )
            
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 1), (-1, -1), True),
            ]))
            
            elements.append(detail_table)
        else:
            elements.append(Paragraph(
                "No se encontraron consultas que cumplan con los criterios de filtrado.", 
                normal_style
            ))
            elements.append(Spacer(1, 0.5*inch))
        
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph(
            "Este reporte fue generado automáticamente por el Sistema de Gestión Médica.",
            small_style
        ))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer


class FiltrosConsultaView(APIView):
    """
    Vista que proporciona opciones para filtrar consultas.
    """
    
    def get(self, request):
        try:
            # Obtener datos de atletas - USANDO SETTINGS
            atletas_response = requests.get(settings.API_ATLETAS, timeout=5)
            atletas_response.raise_for_status()
            
            atletas_dict = {}
            for a in atletas_response.json():
                if a["id"] not in atletas_dict:
                    atletas_dict[a["id"]] = {
                        "id": a["id"], 
                        "nombre": f"{a.get('nombre', '')} {a.get('apPaterno', '')} {a.get('apMaterno', '')}"
                    }
            
            atletas = list(atletas_dict.values())
            
            # Obtener datos de profesionales - USANDO SETTINGS
            profesionales_response = requests.get(settings.API_PROFESIONALES, timeout=5)
            profesionales_response.raise_for_status()
            
            profesionales_dict = {}
            for p in profesionales_response.json():
                if p["id"] not in profesionales_dict:
                    profesionales_dict[p["id"]] = {
                        "id": p["id"], 
                        "nombre": f"{p.get('nombre', '')} {p.get('apPaterno', '')} {p.get('apMaterno', '')} - {p.get('especialidad', '')}"
                    }
            
            profesionales = list(profesionales_dict.values())
            
            response = Response({
                'atletas': atletas,
                'profesionales': profesionales
            })
            
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            
            return response
            
        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Error al conectar con el servicio de datos',
                'detalles': str(e)
            }, status=503)
        
        except Exception as e:
            return Response({
                'error': 'Error interno del servidor',
                'detalles': str(e)
            }, status=500)
            
    def options(self, request):
        """
        Maneja las solicitudes OPTIONS para CORS preflight
        """
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response