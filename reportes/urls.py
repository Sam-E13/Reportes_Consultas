from django.urls import path
from .views import *

urlpatterns = [
    path('generar-reporte-consultas/', GenerarReporteConsultasPDFView.as_view(), name='generar-reporte-consultas'),
    path('api/filtros-consulta/', FiltrosConsultaView.as_view(), name='filtros-consulta'),
    path('api/estadisticas-consultas/', EstadisticasConsultasView.as_view(), name='estadisticas_consultas'),
]