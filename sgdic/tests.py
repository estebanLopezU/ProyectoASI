# =====================================================================
# Pruebas del flujo completo SGDIC (RF/RN críticos + vistas)
# =====================================================================
from datetime import time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from analitica.models import NecesidadDetectada
from analitica.servicios import predecir_materia
from anuncios.models import Anuncio
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


class PruebasCarteleraPorPagina(BaseDatos):
    """La cartelera solo debe verse en el Tablero y en Anuncios (todos los roles)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.anuncio = Anuncio.objects.create(
            titulo="Aviso de prueba", tipo=Anuncio.Tipo.TEXTO,
            cuerpo="Cuerpo del aviso.", creado_por=cls.secretaria)

    def _pagina_tiene_cartelera(self, cliente, url):
        r = cliente.get(url)
        return r.status_code == 200 and 'anuncios-dashboard' in r.content.decode()

    def test_cartelera_visible_solo_en_tablero_y_anuncios(self):
        paginas_sin_cartelera = [
            reverse("materias:catalogo"),
            reverse("mensajes:bandeja"),
            reverse("quejas:mis_quejas"),
            reverse("cupos:mi_horario"),
        ]
        for usuario in (self.estudiante, self.docente, self.secretaria):
            cliente = self.login(usuario)
            # Solo Tablero y Anuncios muestran la cartelera.
            self.assertTrue(self._pagina_tiene_cartelera(cliente, reverse("dashboard")))
            self.assertTrue(self._pagina_tiene_cartelera(cliente, reverse("anuncios:lista")))
            for url in paginas_sin_cartelera:
                self.assertFalse(
                    self._pagina_tiene_cartelera(cliente, url),
                    f"La cartelera apareció en {url} para {usuario.username}")


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


class PruebasAnuncios(BaseDatos):
    """Cartelera institucional: vigencia, roles y permisos de publicación."""

    def setUp(self):
        self.cliente = Client()

    def _anuncio(self, **extra):
        datos = {"titulo": "Aviso", "tipo": "TEXTO", "cuerpo": "Cuerpo",
                 "creado_por": self.docente}
        datos.update(extra)
        return Anuncio.objects.create(**datos)

    def test_login_sin_anuncios_no_muestra_carrusel(self):
        respuesta = self.cliente.get(reverse("usuario:login"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "carruselAnuncios")

    def test_anonimo_ve_anuncio_publico_pero_no_el_restringido(self):
        self._anuncio(titulo="Publico general")
        self._anuncio(titulo="Solo docentes", roles="DOCENTE")
        respuesta = self.cliente.get(reverse("usuario:login"))
        self.assertContains(respuesta, "Publico general")
        self.assertNotContains(respuesta, "Solo docentes")

    def test_dashboard_filtra_por_rol(self):
        self._anuncio(titulo="Para docentes", roles="DOCENTE")
        respuesta = self.login(self.estudiante).get(reverse("dashboard"))
        self.assertNotContains(respuesta, "Para docentes")
        respuesta = self.login(self.docente).get(reverse("dashboard"))
        self.assertContains(respuesta, "Para docentes")

    def test_vigencia_expirada_no_se_muestra(self):
        self._anuncio(titulo="Vencido",
                      visible_hasta=timezone.now() - timedelta(days=1))
        respuesta = self.login(self.estudiante).get(reverse("dashboard"))
        self.assertNotContains(respuesta, "Vencido")

    def test_vigencia_futura_no_se_muestra(self):
        self._anuncio(titulo="Futuro",
                      visible_desde=timezone.now() + timedelta(days=1))
        self.assertEqual(Anuncio.visibles(), [])
        respuesta = self.login(self.estudiante).get(reverse("dashboard"))
        self.assertNotContains(respuesta, "Futuro")

    def test_docente_publica_estudiante_no(self):
        self.assertEqual(self.cliente.get(reverse("anuncios:crear")).status_code, 302)
        self.assertEqual(
            self.login(self.estudiante).get(reverse("anuncios:crear")).status_code, 403)
        self.assertEqual(
            self.login(self.docente).get(reverse("anuncios:crear")).status_code, 200)
        self.assertEqual(
            self.login(self.secretaria).get(reverse("anuncios:lista")).status_code, 200)

    def test_crear_anuncio_desde_vista(self):
        cliente = self.login(self.docente)
        respuesta = cliente.post(reverse("anuncios:crear"), {
            "titulo": "Charla", "tipo": "TEXTO", "cuerpo": "Jueves 10 a.m.",
            "activo": "on",
        })
        self.assertRedirects(respuesta, reverse("anuncios:lista"))
        anuncio = Anuncio.objects.get(titulo="Charla")
        self.assertEqual(anuncio.creado_por, self.docente)
        self.assertTrue(anuncio.activo)

    def test_retirar_anuncio_propio(self):
        anuncio = self._anuncio(titulo="Temporal")
        cliente = self.login(self.docente)
        cliente.post(reverse("anuncios:desactivar", args=[anuncio.pk]))
        anuncio.refresh_from_db()
        self.assertFalse(anuncio.activo)
        self.assertFalse(anuncio.vigente())

    def test_primera_pestana_es_del_anuncio_mas_reciente(self):
        """El banner abre con el anuncio más reciente y su pestaña activa."""
        self._anuncio(titulo="Aviso antiguo")
        self._anuncio(titulo="Imagen nueva", tipo="IMAGEN")
        respuesta = self.login(self.estudiante).get(reverse("dashboard"))
        self.assertEqual(respuesta.context["anuncios_carrusel"][0].titulo,
                         "Imagen nueva")
        self.assertEqual(respuesta.context["anuncios_grupos"][0]["clave"], "IMAGEN")

    def test_cartelera_no_filtra_texto_de_comentarios(self):
        """Los comentarios de la plantilla no deben imprimirse en la página."""
        self._anuncio(titulo="Visible")
        respuesta = self.login(self.estudiante).get(reverse("dashboard"))
        self.assertContains(respuesta, "cartelera-banner")
        self.assertNotContains(respuesta, "Espera en el contexto")

    def test_etiquetas_de_tipo_ocultas_en_toda_la_web(self):
        """Visitante y usuarios ven la misma cartelera: sin chips ni pestañas.

        El Tablero (y Anuncios) usan la misma versión compacta que el login.
        """
        self._anuncio(titulo="Aviso general")
        self._anuncio(titulo="Imagen general", tipo="IMAGEN",
                      enlace="https://ejemplo.test/foto.png")

        respuesta = self.cliente.get(reverse("usuario:login"))
        self.assertContains(respuesta, "cartelera-banner")
        self.assertContains(respuesta, "cartelera-lista")
        self.assertNotContains(respuesta, 'class="cartelera-chip"')
        self.assertNotContains(respuesta, "cartelera-pestanas")

        # BaseDatos no crea usuario ADMIN: lo damos de alta aquí.
        admin = Usuario.objects.create_user(
            username="admin_cartelera", password=CLAVE, rol="ADMIN",
            email="admin_c@test.co")

        # Todos los roles, en Tablero y en Anuncios: sin chips ni pestañas.
        for usuario in (self.estudiante, self.docente, self.secretaria, admin):
            for url in (reverse("dashboard"), reverse("anuncios:lista")):
                respuesta = self.login(usuario).get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "cartelera-banner")
                self.assertContains(respuesta, "cartelera-lista")
                self.assertNotContains(
                    respuesta, "cartelera-pestanas",
                    msg_prefix=f"pestanas en {url} para {usuario.username}")
                self.assertNotContains(
                    respuesta, 'class="cartelera-chip"',
                    msg_prefix=f"chip en {url} para {usuario.username}")


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
        self.assertIn("malla", datos)
        datos_staff = tablero_kpis(usuario=self.secretaria)
        self.assertIn("abiertos", datos_staff)
        self.assertIn("ocupacion_promedio", datos_staff)


class PruebasMallaCurricular(BaseDatos):
    """Maya curricular: semáforo verde/amarillo/rojo y edición por rol."""

    def test_estado_derivado_desde_inscripciones(self):
        from materias.models import MallaCurricular

        # Sin inscripción → rojo (pendiente)
        fila = MallaCurricular.objects.create(
            estudiante=self.estudiante, materia=self.intro, semestre=1)
        self.assertEqual(fila.color, "rojo")
        self.assertEqual(fila.estado_efectivo, MallaCurricular.Estado.PENDIENTE)

        # Con inscripción aprobada → verde (vista)
        inscripcion = Inscripcion.objects.create(
            estudiante=self.estudiante, oferta=self.oferta_intro,
            estado=Inscripcion.Estado.APROBADA)
        self.assertEqual(fila.color, "verde")
        self.assertEqual(fila.etiqueta_corta, "Vista")

        # Con inscripción activa → amarillo (en curso)
        inscripcion.estado = Inscripcion.Estado.ACTIVA
        inscripcion.save()
        self.assertEqual(fila.color, "amarillo")
        self.assertEqual(fila.etiqueta_corta, "Cursando")

    def test_estado_manual_prevalece_sobre_derivado(self):
        from materias.models import MallaCurricular

        fila = MallaCurricular.objects.create(
            estudiante=self.estudiante, materia=self.intro, semestre=1,
            estado=MallaCurricular.Estado.VISTA)
        # No hay inscripciones, pero el administrativo fijó "vista"
        self.assertEqual(fila.estado_derivado, MallaCurricular.Estado.PENDIENTE)
        self.assertEqual(fila.estado_efectivo, MallaCurricular.Estado.VISTA)
        self.assertEqual(fila.color, "verde")

    def test_estudiante_ve_su_malla_y_no_puede_editar(self):
        cliente = self.login(self.estudiante)
        respuesta = cliente.get(reverse("materias:malla", args=[self.estudiante.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Malla curricular")
        # La malla de otro estudiante no es accesible
        otro = Usuario.objects.create_user(username="otro", password=CLAVE,
                                            rol="ESTUDIANTE")
        respuesta = cliente.get(reverse("materias:malla", args=[otro.pk]))
        self.assertEqual(respuesta.status_code, 403)
        # El estudiante no puede entrar a editar la malla
        respuesta = cliente.post(
            reverse("materias:malla_editar", args=[self.estudiante.pk]),
            {"materia": self.intro.pk, "semestre": 1, "estado": "VISTA"})
        self.assertEqual(respuesta.status_code, 403)

    def test_administrativo_edita_la_malla(self):
        from materias.models import MallaCurricular

        cliente = self.login(self.secretaria)
        respuesta = cliente.get(reverse("usuario:mallas"))
        self.assertEqual(respuesta.status_code, 200)
        respuesta = cliente.post(
            reverse("materias:malla_editar", args=[self.estudiante.pk]),
            {"materia": self.intro.pk, "semestre": 2, "estado": "VISTA",
             "observacion": "Regularizada"})
        self.assertEqual(respuesta.status_code, 302)
        fila = MallaCurricular.objects.get(estudiante=self.estudiante,
                                           materia=self.intro)
        self.assertEqual(fila.semestre, 2)
        self.assertEqual(fila.estado, MallaCurricular.Estado.VISTA)
        self.assertEqual(fila.actualizado_por, self.secretaria)
        # Queda auditoría y notificación al estudiante
        from comun.models import AuditoriaLog, Notificacion

        self.assertTrue(AuditoriaLog.objects.filter(
            accion="EDITAR_MALLA_CURRICULAR").exists())
        self.assertTrue(Notificacion.objects.filter(
            destinatario=self.estudiante, titulo__contains="Malla").exists())

    def test_docente_solo_consulta_mallas_de_sus_estudiantes(self):
        cliente = self.login(self.docente)
        respuesta = cliente.get(reverse("materias:malla", args=[self.estudiante.pk]))
        self.assertEqual(respuesta.status_code, 403)
        # Al inscribirse el estudiante en una materia del docente, ya puede verla
        Inscripcion.objects.create(estudiante=self.estudiante,
                                   oferta=self.oferta_intro)
        respuesta = cliente.get(reverse("materias:malla", args=[self.estudiante.pk]))
        self.assertEqual(respuesta.status_code, 200)


