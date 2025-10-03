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
            # URLs de los servicios
            API_CONSULTAS = 'http://backend:8000/Modulos/Consultas/'
            API_PROFESIONALES = 'http://backend:8000/Catalogos/Profesionales-Salud/'
            API_ATLETAS = 'http://backend:8000/Catalogos/Atletas/'
            
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
            
            # 6. Datos mensuales por profesional (últimos 12 meses) - CORREGIDO
            monthly_data_by_profesional = []
            meses_mostrar = 12  # Mostrar datos de los últimos 12 meses
            
            for i in range(meses_mostrar):
                # Calcular mes y año para el período actual (manteniendo lógica original)
                mes_offset = meses_mostrar - i - 1
                month = (mes_actual - mes_offset - 1) % 12 + 1
                year = año_actual - (1 if mes_actual - mes_offset - 1 < 0 else 0)
                
                # Filtrar consultas para este mes
                consultas_mes = [
                    c for c in todas_consultas 
                    if datetime.strptime(c['fecha'], '%Y-%m-%d').month == month
                    and datetime.strptime(c['fecha'], '%Y-%m-%d').year == year
                ]
                
                # Contar consultas por profesional para este mes
                profesionales_data_mes = []
                for profesional in todos_profesionales:
                    profesional_id = str(profesional['id'])
                    # CORREGIDO: usar 'profesional_salud' en lugar de 'profesional_salud_id'
                    count = sum(1 for c in consultas_mes 
                              if str(c.get('profesional_salud', c.get('profesional_salud_id', ''))) == profesional_id)
                    
                    # Crear nombre completo del profesional
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
            
            # Ordenar por fecha (más antigua primero) - MANTENER ORDEN ORIGINAL
            # monthly_data_by_profesional.reverse()  # Comentado para mantener orden original
            
            # 7. Datos totales por profesional (para el gráfico simple) - CORREGIDO
            profesionales_data = []
            for profesional in todos_profesionales:
                profesional_id = str(profesional['id'])
                # CORREGIDO: usar 'profesional_salud' en lugar de 'profesional_salud_id'
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
            
            # 8. Datos por atleta (top 10 con más consultas) - CORREGIDO
            atletas_data = []
            for atleta in todos_atletas:
                atleta_id = str(atleta['id'])
                # CORREGIDO: usar 'atleta' en lugar de 'atleta_id'
                total_consultas_atleta = sum(
                    1 for c in todas_consultas 
                    if str(c.get('atleta', c.get('atleta_id', ''))) == atleta_id
                )
                
                nombre_completo = f"{atleta.get('nombre', '')} {atleta.get('apPaterno', '')}".strip()
                
                # Solo agregar atletas que tienen consultas
                if total_consultas_atleta > 0:
                    atletas_data.append({
                        'nombre': nombre_completo,
                        'id': atleta_id,
                        'total': total_consultas_atleta
                    })
            
            # Ordenar y tomar top 10
            top_atletas = sorted(atletas_data, key=lambda x: x['total'], reverse=True)[:10]
            
            # 9. Distribución por diagnóstico común (simplificado)
            diagnosticos = {}
            for consulta in todas_consultas:
                diagnostico = consulta.get('diagnostico', 'Sin diagnóstico').strip()
                if diagnostico and diagnostico != 'Sin diagnóstico':
                    diagnosticos[diagnostico] = diagnosticos.get(diagnostico, 0) + 1
            
            top_diagnosticos = sorted(
                [{'nombre': k, 'total': v} for k, v in diagnosticos.items()], 
                key=lambda x: x['total'], 
                reverse=True
            )[:5]  # Top 5 diagnósticos
            
            # Log para debugging - AGREGADO PARA VERIFICAR DATOS
            logger.info(f"Total consultas procesadas: {len(todas_consultas)}")
            logger.info(f"Profesionales encontrados: {len(todos_profesionales)}")
            logger.info(f"Atletas encontrados: {len(todos_atletas)}")
            
            # Log de ejemplo de datos para verificar estructura
            if todas_consultas:
                logger.info(f"Ejemplo de consulta: {todas_consultas[0]}")
            if todos_profesionales:
                logger.info(f"Ejemplo de profesional: {todos_profesionales[0]}")
            if todos_atletas:
                logger.info(f"Ejemplo de atleta: {todos_atletas[0]}")
                
            logger.info(f"Atletas con consultas: {len(top_atletas)}")
            logger.info(f"Meses de datos: {len(monthly_data_by_profesional)}")
            
            # Log de algunos top atletas
            if top_atletas:
                logger.info(f"Top 3 atletas: {top_atletas[:3]}")
            
            # Respuesta final
            return Response({
                'total_consultas': len(todas_consultas),  # Total histórico
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
            
logger = logging.getLogger(__name__)

class GenerarReporteConsultasPDFView(APIView):
    """
    Vista que genera reportes PDF de consultas médicas con filtros aplicables.
    """

    # Configuración de endpoints
    CONSULTAS_API_URL = 'http://backend:8000/Modulos/Consultas/'
    CATALOGOS_API_URL = 'http://backend:8000/Catalogos/'
    TIMEOUT = 10  # segundos

    def post(self, request):
        """
        Genera un reporte PDF de consultas médicas con filtros aplicables.
        
        Parámetros esperados en request.data:
        - fecha_inicio (requerido): Fecha de inicio (YYYY-MM-DD)
        - fecha_fin (requerido): Fecha de fin (YYYY-MM-DD)
        - atleta_id (opcional): ID del atleta para filtrar
        - profesional_id (opcional): ID del profesional para filtrar
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
                # Modificado: Añadir parámetros de filtro directamente a la solicitud
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
                return catalogos  # Retorna el error si hubo problema

            # 4. Filtrar consultas según parámetros
            # Modificado: Mejorar el filtrado para ser más flexible con los formatos
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
            
            # Añadir encabezados CORS
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
        
        Returns:
            dict: Diccionario con los catálogos o Response con error
        """
        catalogos = {
            'atletas': {},
            'profesionales': {}
        }
        
        try:
            # Obtener atletas
            response = requests.get(
                f"{self.CATALOGOS_API_URL}Atletas/",
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            for atleta in response.json():
                catalogos['atletas'][str(atleta['id'])] = atleta
            
            # Obtener profesionales
            response = requests.get(
                f"{self.CATALOGOS_API_URL}Profesionales-Salud/",
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
        
        Args:
            consultas (list): Lista de consultas a filtrar
            filtros (dict): Parámetros de filtrado
            catalogos (dict): Catálogos para validar IDs
            
        Returns:
            list: Lista de consultas filtradas
        """
        # Modificado: Mejorar el manejo de fechas para ser más flexible
        try:
            fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d')
            fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').replace(
                hour=23, minute=59, second=59
            )
        except ValueError as e:
            logger.error("Error al parsear fechas: %s", str(e))
            # Si hay error en el formato de fecha, devolver todas las consultas
            return consultas
        
        consultas_filtradas = []
        
        for consulta in consultas:
            try:
                # 1. Filtrar por fecha - Manejar múltiples formatos posibles
                fecha_consulta = None
                fecha_campos = ['fecha', 'creado_el', 'fecha_consulta', 'created_at']
                
                for campo in fecha_campos:
                    if campo in consulta and consulta[campo]:
                        try:
                            # Intentar varios formatos de fecha
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
                
                # Si no se pudo determinar la fecha, incluir la consulta
                if not fecha_consulta:
                    logger.warning("No se pudo determinar la fecha para consulta %s", consulta.get('id', 'desconocido'))
                    consultas_filtradas.append(consulta)
                    continue
                
                if not (fecha_inicio <= fecha_consulta <= fecha_fin):
                    continue
                
                # 2. Filtrar por atleta si se especificó
                if 'atleta_id' in filtros and filtros['atleta_id'] not in [None, "todos", ""]:
                    # Obtener el ID del atleta de la consulta - más flexible
                    atleta_id_consulta = self._obtener_id_de_campo(consulta, ['atleta_id', 'atleta', 'id_atleta', 'paciente_id', 'paciente'])
                    
                    if not atleta_id_consulta or str(atleta_id_consulta) != str(filtros['atleta_id']):
                        continue
                
                # 3. Filtrar por profesional si se especificó
                if 'profesional_id' in filtros and filtros['profesional_id'] not in [None, "todos", ""]:
                    # Obtener el ID del profesional de la consulta - más flexible
                    profesional_id_consulta = self._obtener_id_de_campo(consulta, ['profesional_salud_id', 'profesional_salud', 'profesional_id', 'profesional', 'id_profesional', 'medico_id', 'medico'])
                    
                    if not profesional_id_consulta or str(profesional_id_consulta) != str(filtros['profesional_id']):
                        continue
                
                # Si pasó todos los filtros, agregar a la lista
                consultas_filtradas.append(consulta)
                
            except Exception as e:
                logger.warning("Error al procesar consulta %s: %s", consulta.get('id', 'desconocido'), str(e))
                # Incluir la consulta si hay error en el procesamiento
                consultas_filtradas.append(consulta)
                continue
                
        return consultas_filtradas

    def _enriquecer_consultas(self, consultas, catalogos):
        """
        Enriquece las consultas con información de catálogos.
        
        Args:
            consultas (list): Lista de consultas a enriquecer
            catalogos (dict): Catálogos con información adicional
            
        Returns:
            list: Lista de consultas enriquecidas
        """
        consultas_enriquecidas = []
        
        for consulta in consultas:
            # Modificado: Buscar el diagnóstico en diferentes campos posibles
            diagnostico = "No especificado"
            for campo in ['diagnostico', 'diagnóstico', 'diagnostic']:
                if campo in consulta and consulta[campo]:
                    diagnostico = consulta[campo]
                    break
            
            # Modificado: Buscar el tratamiento en diferentes campos posibles
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
        
        Args:
            consulta (dict): Objeto consulta
            
        Returns:
            str: Fecha de consulta o cadena vacía
        """
        fecha_campos = ['fecha', 'creado_el', 'fecha_consulta', 'created_at']
        for campo in fecha_campos:
            if campo in consulta and consulta[campo]:
                return consulta[campo]
        return ""
        
    def _obtener_id_de_campo(self, objeto, posibles_campos):
        """
        Obtiene el ID de un campo que puede estar en diferentes formatos.
        
        Args:
            objeto (dict): Objeto que contiene el campo
            posibles_campos (list): Lista de posibles nombres del campo
            
        Returns:
            str: ID encontrado o None
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
        
        Args:
            fecha_str (str): Fecha en formato ISO
            
        Returns:
            str: Fecha formateada
        """
        if not fecha_str:
            return "Fecha no disponible"
            
        try:
            # Intentar varios formatos de fecha
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
        Genera un PDF con la información de las consultas con mejor presentación.
        
        Args:
            consultas (list): Lista de consultas con datos enriquecidos
            filtros (dict): Filtros aplicados
                
        Returns:
            BytesIO: Buffer con el PDF generado
        """
        buffer = io.BytesIO()
        
        # Configuración del documento con márgenes adecuados
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        # Estilos
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
        
        # Elementos del documento
        elements = []
        
        # 1. Encabezado
        elements.append(Paragraph("Reporte de Consultas Médicas", title_style))
        elements.append(Paragraph(
            f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
            small_style
        ))
        elements.append(Spacer(1, 0.25*inch))
        
        # 2. Filtros aplicados
        elements.append(Paragraph("Filtros Aplicados:", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Fechas formateadas
        fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').strftime('%d/%m/%Y')
        fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').strftime('%d/%m/%Y')
        elements.append(Paragraph(f"Período: {fecha_inicio} - {fecha_fin}", normal_style))
        
        # Filtros específicos
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
        
        # 3. Estadísticas resumidas
        elements.append(Paragraph("Resumen Estadístico:", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Calcular estadísticas
        total = len(consultas)
        
        # Contar consultas por profesional
        profesionales = {}
        for consulta in consultas:
            profesional = consulta['profesional_nombre']
            if profesional in profesionales:
                profesionales[profesional] += 1
            else:
                profesionales[profesional] = 1
        
        # Tabla de estadísticas
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),  # Azul moderno
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, 1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#EFF6FF')),  # Azul claro
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BFDBFE')),    # Borde azul claro
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.25*inch))
        
        # 4. Detalle de consultas
        if consultas:
            elements.append(Paragraph("Detalle de Consultas:", subtitle_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Encabezados de tabla
            detail_headers = [
                "Fecha", 
                "Atleta", 
                "Profesional", 
                "Diagnóstico", 
                "Tratamiento"
            ]
            
            # Datos de la tabla
            detail_data = [detail_headers]
            
            for consulta in consultas:
                detail_data.append([
                    consulta.get('fecha', 'No especificada'),
                    consulta.get('atleta_nombre', 'No especificado'),
                    consulta.get('profesional_nombre', 'No especificado'),
                    Paragraph(consulta.get('diagnostico', 'No especificado'), styles['Normal']),
                    Paragraph(consulta.get('tratamiento', 'No especificado'), styles['Normal'])
                ])
            
            # Crear tabla con anchos de columna ajustados
            detail_table = Table(
                detail_data, 
                colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 2.0*inch, 2.0*inch],
                repeatRows=1  # Repetir encabezados en cada página
            )
            
            # Estilo de la tabla
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),  # Azul moderno
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),  # Gris claro
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 1), (-1, -1), True),  # Ajuste de texto
            ]))
            
            elements.append(detail_table)
        else:
            elements.append(Paragraph(
                "No se encontraron consultas que cumplan con los criterios de filtrado.", 
                normal_style
            ))
            elements.append(Spacer(1, 0.5*inch))
        
        # 5. Pie de página
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph(
            "Este reporte fue generado automáticamente por el Sistema de Gestión Médica.",
            small_style
        ))
        
        # Construir el documento
        doc.build(elements)
        buffer.seek(0)
        return buffer

class FiltrosConsultaView(APIView):
    """
    Vista que proporciona opciones para filtrar consultas.
    """
    
    def get(self, request):
        # URL del endpoint para obtener datos de filtros
        API_URL_BASE = 'http://backend:8000/Catalogos/'
        
        try:
            # Obtener datos de atletas
            atletas_response = requests.get(f"{API_URL_BASE}Atletas/", timeout=5)
            atletas_response.raise_for_status()
            
            # Usar un diccionario para eliminar duplicados por ID
            atletas_dict = {}
            for a in atletas_response.json():
                if a["id"] not in atletas_dict:
                    atletas_dict[a["id"]] = {"id": a["id"], "nombre": f"{a.get('nombre', '')} {a.get('apPaterno', '')} {a.get('apMaterno', '')}"}
            
            atletas = list(atletas_dict.values())
            
            # Obtener datos de profesionales de salud
            profesionales_response = requests.get(f"{API_URL_BASE}Profesionales-Salud/", timeout=5)
            profesionales_response.raise_for_status()
            
            # Usar un diccionario para eliminar duplicados por ID
            profesionales_dict = {}
            for p in profesionales_response.json():
                if p["id"] not in profesionales_dict:
                    profesionales_dict[p["id"]] = {
                        "id": p["id"], 
                        "nombre": f"{p.get('nombre', '')} {p.get('apPaterno', '')} {p.get('apMaterno', '')} - {p.get('especialidad', '')}"
                    }
            
            profesionales = list(profesionales_dict.values())
            
            # Añadir encabezados CORS
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