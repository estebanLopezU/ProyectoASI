# =====================================================================
# Pruebas del flujo completo SGDIC (RF/RN críticos + vistas)
# =====================================================================
from datetime import time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from analitica.models import NecesidadDetectada
from analitica.servicios import predecir_materia
from cupos.models import Inscripcion, OfertaCupo, SolicitudCupo
from quejas.models import CategoriaQueja, Queja
from usuario.models import Usuario

CLAVE = "Prueba2026*"


class BaseDatos(TestCase):
    """Datos mínimos compartidos por las pruebas."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username="docente", password=CLAVE, rol="DOCENTE",
            first_name="Julia", last_name="López", email="docente@test.co")
        cls.estudiante = Usuario.objects.create_user(
            username="estudiante", password=CLAVE, rol="ESTUDIANTE",
            first_name="Ana", last_name="Torres", email="ana@test.co",
            semestre=6, promedio=4.2)
        cls.secretaria = Usuario.objects.create_user(
            username="secretaria", password=CLAVE, rol="SECRETARIA",
            email="sec@test.co")
        from materias.models import Materia

        cls.intro = Materia.objects.create(
            codigo="ISC-101", nombre="Introducción", creditos=3,
            estado=Materia.Estado.PUBLICADA)
        cls.intro.docentes.add(cls.docente)
        cls.avanzada = Materia.objects.create(
            codigo="ISC-201", nombre="Avanzada", creditos=3,
            estado=Materia.Estado.PUBLICADA)
        cls.avanzada.docentes.add(cls.docente)
        cls.avanzada.prerrequisitos.add(cls.intro)
        cls.oferta_intro = OfertaCupo.objects.create(
            materia=cls.intro, periodo="2026-1", cupo_maximo=30,
            dia=1, hora_inicio=time(7, 0), hora_fin=time(9, 0))
        cls.oferta_avanzada = OfertaCupo.objects.create(
            materia=cls.avanzada, periodo="2026-1", cupo_maximo=2,
            dia=1, hora_inicio=time(7, 0), hora_fin=time(9, 0))
        cls.oferta_conflicto = OfertaCupo.objects.create(
            materia=cls.intro, periodo="2026-2", cupo_maximo=5,
            dia=1, hora_inicio=time(8, 0), hora_fin=time(10, 0))

    def login(self, usuario):
        cliente = Client()
        cliente.login(username=usuario.username, password=CLAVE)
        return cliente


class PruebasReglasCupo(BaseDatos):
    """RN-01 a RN-04 en SolicitudCupo.procesar()."""

    def _con_prerrequisito_aprobado(self):
        historico = OfertaCupo.objects.create(
            materia=self.intro, periodo="2025-1", cupo_maximo=30,
            dia=2, hora_inicio=time(7, 0), hora_fin=time(9, 0))
        Inscripcion.objects.create(
            estudiante=self.estudiante, oferta=historico,
            estado=Inscripcion.Estado.APROBADA)

    def test_rn01_rechaza_sin_prerrequisitos(self):
        solicitud = SolicitudCupo.objects.create(
            oferta=self.oferta_avanzada, estudiante=self.estudiante)
        solicitud.procesar()
        self.assertEqual(solicitud.estado, SolicitudCupo.Estado.RECHAZADA)
        self.assertIn("RN-01", solicitud.justificacion_estado)

    def test_rn01_aprueba_con_prerrequisitos(self):
        self._con_prerrequisito_aprobado()
        solicitud = SolicitudCupo.objects.create(
            oferta=self.oferta_avanzada, estudiante=self.estudiante)
        solicitud.procesar()
        self.assertEqual(solicitud.estado, SolicitudCupo.Estado.APROBADA)
        self.oferta_avanzada.refresh_from_db()
        self.assertEqual(self.oferta_avanzada.inscritos, 1)

    def test_rn03_rechaza_por_conflicto_horario(self):
        Inscripcion.objects.create(
            estudiante=self.estudiante, oferta=self.oferta_intro,
            estado=Inscripcion.Estado.ACTIVA)
        solicitud = SolicitudCupo.objects.create(
            oferta=self.oferta_conflicto, estudiante=self.estudiante)
        solicitud.procesar()
        self.assertEqual(solicitud.estado, SolicitudCupo.Estado.RECHAZADA)
        self.assertIn("RN-03", solicitud.justificacion_estado)

    def test_rn02_envia_a_lista_de_espera(self):
        self.oferta_avanzada.cupo_maximo = 1
        self.oferta_avanzada.inscritos = 1
        self.oferta_avanzada.save()
        self._con_prerrequisito_aprobado()
        solicitud = SolicitudCupo.objects.create(
            oferta=self.oferta_avanzada, estudiante=self.estudiante)
        solicitud.procesar()
        self.assertEqual(solicitud.estado, SolicitudCupo.Estado.EN_ESPERA)
        self.assertIn("RN-02", solicitud.justificacion_estado)


class PruebasAnalitica(BaseDatos):
    """Score (I×U)/(E+ε) del Cap. 6."""

    def test_score_formula(self):
        necesidad = NecesidadDetectada(impacto="CRITICO", urgencia="DOCENTE",
                                       esfuerzo=8)
        # (4 × 1.5) / (8 + 0.5) = 0.7059
        self.assertEqual(necesidad.calcular_score(), 0.7059)

    def test_niveles_prioridad(self):
        self.assertEqual(NecesidadDetectada.clasificar(2.5), "CRITICA")
        self.assertEqual(NecesidadDetectada.clasificar(0.7), "ALTA")
        self.assertEqual(NecesidadDetectada.clasificar(0.3), "MEDIA")
        self.assertEqual(NecesidadDetectada.clasificar(0.1), "BAJA")

    def test_prediccion_promedio_movil(self):
        for periodo, inscritos in (("2024-1", 10), ("2024-2", 20), ("2025-1", 30)):
            OfertaCupo.objects.create(materia=self.intro, periodo=periodo,
                                      cupo_maximo=40, inscritos=inscritos)
        prediccion = predecir_materia(self.intro)
        self.assertIsNotNone(prediccion)
        self.assertGreater(prediccion.demanda_estimada, 0)
        self.assertGreaterEqual(prediccion.cupo_sugerido, 1)


class PruebasQuejas(BaseDatos):
    """RN-10 escalamiento, RN-11 soluciones rápidas y RN-12 cierre."""

    def test_rn10_escala_por_vencimiento(self):
        categoria = CategoriaQueja.objects.create(nombre="Tecnológica")
        queja = Queja.objects.create(
            radicada_por=self.estudiante, categoria=categoria,
            asunto="Falla", descripcion="No funciona")
        self.assertFalse(queja.requiere_escalamiento())
        queja.creada = timezone.now() - timedelta(days=4)
        queja.save()
        self.assertTrue(queja.requiere_escalamiento())
        self.assertTrue(queja.escalar())
        self.assertEqual(queja.estado, Queja.Estado.ESCALADO)

    def test_rn11_solucion_rapida_resuelve(self):
        categoria = CategoriaQueja.objects.create(
            nombre="Trámites", solucion_rapida="Habilitado de inmediato.")
        queja = Queja.objects.create(
            radicada_por=self.estudiante, categoria=categoria,
            asunto="Certificado", descripcion="Necesito certificado")
        self.assertTrue(queja.aplicar_solucion_rapida(self.secretaria))
        self.assertEqual(queja.estado, Queja.Estado.RESUELTO)
        self.assertTrue(queja.seguimientos.filter(detalle__contains="RN-11").exists())

    def test_rn12_cierre_con_confirmacion(self):
        categoria = CategoriaQueja.objects.create(nombre="Académica")
        queja = Queja.objects.create(
            radicada_por=self.estudiante, categoria=categoria,
            asunto="Nota", descripcion="Revisión")
        queja.asignar(self.docente)
        queja.resolver(self.docente, "Corregida")
        queja.confirmar_cierre(satisfaccion=5)
        self.assertEqual(queja.estado, Queja.Estado.CERRADO)
        self.assertEqual(queja.satisfaccion, 5)

    def test_consecutivo_unico(self):
        categoria = CategoriaQueja.objects.create(nombre="Otra")
        primera = Queja.objects.create(radicada_por=self.estudiante,
                                       categoria=categoria, asunto="A", descripcion="A")
        segunda = Queja.objects.create(radicada_por=self.estudiante,
                                       categoria=categoria, asunto="B", descripcion="B")
        self.assertNotEqual(primera.consecutivo, segunda.consecutivo)
        self.assertTrue(primera.consecutivo.startswith("Q-"))


class PruebasVistas(BaseDatos):
    """Autenticación, RBAC y renderizado de las páginas principales."""

    def test_login_y_dashboard(self):
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "dashboard_estudiante.html")

    def test_dashboard_requiere_sesion(self):
        respuesta = Client().get(reverse("dashboard"))
        self.assertEqual(respuesta.status_code, 302)

    def test_catalogo_publico(self):
        respuesta = Client().get(reverse("materias:catalogo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Introducción")

    def test_ofertas_y_solicitud_de_cupo(self):
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("cupos:ofertas"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Avanzada")
        respuesta = cliente.post(reverse("cupos:solicitar", args=[self.oferta_intro.pk]))
        self.assertRedirects(respuesta, reverse("cupos:mis_solicitudes"))
        self.assertTrue(SolicitudCupo.objects.filter(
            estudiante=self.estudiante, oferta=self.oferta_intro).exists())

    def test_panel_staff_requiere_rol(self):
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("cupos:lista_espera"))
        self.assertEqual(respuesta.status_code, 403)
        cliente_staff = self.login(self.secretaria)
        respuesta = cliente_staff.get(reverse("cupos:lista_espera"))
        self.assertEqual(respuesta.status_code, 200)

    def test_bandeja_de_mensajes(self):
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("mensajes:bandeja"))
        self.assertEqual(respuesta.status_code, 200)

    def test_notificaciones_marca_leido(self):
        from comun.models import Notificacion

        Notificacion.enviar(self.estudiante, "Prueba", "Cuerpo", correo=False)
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("notificaciones"))
        self.assertEqual(respuesta.status_code, 200)
        notificacion = Notificacion.objects.first()
        respuesta = cliente.post(reverse("notificacion_ir", args=[notificacion.pk]))
        notificacion.refresh_from_db()
        self.assertTrue(notificacion.leida)

    def test_radicar_queja_y_trazabilidad(self):
        categoria = CategoriaQueja.objects.create(nombre="Prueba")
        cliente = self.login(self.estudiante)
        respuesta = cliente.post(reverse("quejas:radicar"), {
            "categoria": categoria.pk, "asunto": "Problema X",
            "descripcion": "Detalle del problema", "prioridad": "MEDIA",
        })
        self.assertEqual(respuesta.status_code, 302)
        queja = Queja.objects.get(asunto="Problema X")
        self.assertEqual(queja.estado, Queja.Estado.ABIERTO)
        respuesta = cliente.get(reverse("quejas:detalle", args=[queja.pk]))
        self.assertEqual(respuesta.status_code, 200)

    def test_tablero_kpis_por_rol(self):
        from comun.kpi import tablero_kpis

        datos = tablero_kpis(usuario=self.estudiante)
        self.assertIn("inscripciones_activas", datos)
        datos_staff = tablero_kpis(usuario=self.secretaria)
        self.assertIn("abiertos", datos_staff)
        self.assertIn("ocupacion_promedio", datos_staff)


