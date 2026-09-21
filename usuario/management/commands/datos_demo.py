# =====================================================================
# Comando: python manage.py datos_demo
# Crea usuarios, materias, ofertas, sesiones, quejas y periodos de
# evaluación para probar el sistema completo.
# =====================================================================
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analitica.models import NecesidadDetectada
from cupos.models import Inscripcion, OfertaCupo, SolicitudCupo
from evaluaciones.models import (Falta, InvitacionEvaluacion, PeriodoEvaluacion,
                                 RespuestaEvaluacion, ResumenInasistencia, Sesion)
from materias.models import Materia
from mensajes.models import Hilo, Mensaje
from quejas.models import CategoriaQueja, Queja
from reportes.models import PlantillaReporte
from usuario.models import Usuario

CLAVE = "Sgdic2026*"


class Command(BaseCommand):
    help = "Carga datos de demostración para el SGDIC (idempotente)."

    def handle(self, *args, **opciones):
        self.stdout.write("Creando usuarios…")
        usuarios = self._usuarios()
        self.stdout.write("Creando materias y ofertas…")
        materias, ofertas = self._materias(usuarios)
        self.stdout.write("Creando inscripciones y solicitudes…")
        self._matricula(usuarios, ofertas)
        self.stdout.write("Creando sesiones y faltas…")
        self._asistencia(usuarios, ofertas)
        self.stdout.write("Creando mensajería…")
        self._mensajes(usuarios, materias)
        self.stdout.write("Creando quejas y categorías…")
        self._quejas(usuarios, materias)
        self.stdout.write("Creando periodo de evaluación y respuestas…")
        self._evaluacion(usuarios, materias, ofertas)
        self.stdout.write("Creando plantillas de reporte…")
        self._plantillas()
        self.stdout.write("Ejecutando detección analítica…")
        from analitica.servicios import (detectar_necesidades_de_cupos,
                                         detectar_necesidades_de_inasistencia,
                                         detectar_necesidades_de_quejas,
                                         predecir_todas)

        periodo_actual = "2026-1"
        detectar_necesidades_de_quejas(periodo_actual, minimo=1)
        detectar_necesidades_de_cupos(periodo_actual, minimo_solicitudes=2)
        detectar_necesidades_de_inasistencia(periodo_actual)
        predecir_todas()
        self.stdout.write(self.style.SUCCESS(
            f"Datos demo cargados. Usuarios: {Usuario.objects.count()} · "
            f"Materias: {Materia.objects.count()} · "
            f"Quejas: {Queja.objects.count()} · "
            f"Necesidades: {NecesidadDetectada.objects.count()}"))
        self.stdout.write(f"Contraseña para todos los usuarios demo: {CLAVE}")

    # ------------------------------------------------------------------
    def _usuario(self, username, nombre, apellido, rol, **extra):
        usuario, creado = Usuario.objects.get_or_create(
            username=username,
            defaults={"first_name": nombre, "last_name": apellido, "rol": rol,
                      "email": f"{username}@sgdic.edu.co", **extra},
        )
        if creado:
            usuario.set_password(CLAVE)
            usuario.save()
        return usuario

    def _usuarios(self):
        admin = Usuario.objects.filter(username="admin_sgdic").first()
        if not admin:
            admin = Usuario.objects.create_superuser(
                username="admin_sgdic", email="admin@sgdic.edu.co", password=CLAVE,
                first_name="Administrador", last_name="SGDIC", rol="ADMIN")
        return {
            "admin": admin,
            "secretaria": self._usuario("secretaria", "Sofía", "Ramírez", "SECRETARIA"),
            "jefe": self._usuario("jefe_departamento", "Ricardo", "Peña", "DEPARTAMENTO"),
            "docente1": self._usuario("jlopez", "Julia", "López", "DOCENTE",
                                      area="Ingeniería de Software"),
            "docente2": self._usuario("mgarcia", "Mario", "García", "DOCENTE",
                                      area="Redes y Seguridad"),
            "estudiante1": self._usuario("esteban", "Esteban", "López", "ESTUDIANTE",
                                         semestre=7, promedio=4.35,
                                         codigo_institucional="20221001"),
            "estudiante2": self._usuario("ana", "Ana", "Torres", "ESTUDIANTE",
                                         semestre=5, promedio=4.10,
                                         codigo_institucional="20221002"),
            "estudiante3": self._usuario("carlos", "Carlos", "Mejía", "ESTUDIANTE",
                                         semestre=3, promedio=3.60,
                                         codigo_institucional="20221003"),
        }

    def _materia(self, codigo, nombre, creditos, docentes, prerrequisitos=()):
        materia, _ = Materia.objects.get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "creditos": creditos,
                      "cupo_maximo": 30, "estado": Materia.Estado.PUBLICADA},
        )
        materia.docentes.set(docentes)
        if prerrequisitos:
            materia.prerrequisitos.set(prerrequisitos)
        return materia

    def _materias(self, usuarios):
        intro = self._materia("ISC-101", "Introducción a la Programación", 4,
                              [usuarios["docente1"]])
        estructuras = self._materia("ISC-201", "Estructuras de Datos", 4,
                                    [usuarios["docente1"]], [intro])
        bases = self._materia("ISC-301", "Bases de Datos", 3,
                              [usuarios["docente1"]], [estructuras])
        redes = self._materia("ISC-302", "Redes de Computadores", 3,
                              [usuarios["docente2"]], [estructuras])
        ia = self._materia("ISC-401", "Inteligencia Artificial", 3,
                           [usuarios["docente2"]], [estructuras])
        materias = [intro, estructuras, bases, redes, ia]

        ofertas = []
        horarios = [(1, time(7, 0), time(9, 0)), (1, time(9, 0), time(11, 0)),
                    (2, time(7, 0), time(9, 0)), (3, time(14, 0), time(16, 0)),
                    (4, time(10, 0), time(12, 0))]
        for materia, (dia, inicio, fin) in zip(materias, horarios):
            for periodo, cupo in (("2025-1", 30), ("2025-2", 30), ("2026-1", 25)):
                oferta, _ = OfertaCupo.objects.get_or_create(
                    materia=materia, periodo=periodo,
                    defaults={"cupo_maximo": cupo, "dia": dia,
                              "hora_inicio": inicio, "hora_fin": fin},
                )
                ofertas.append(oferta)
        return materias, ofertas

    def _matricula(self, usuarios, ofertas):
        """Historial de periodos cerrados (para predicción) y matrícula vigente."""
        estudiantes = [usuarios["estudiante1"], usuarios["estudiante2"],
                       usuarios["estudiante3"]]
        for oferta in ofertas:
            if oferta.periodo in ("2025-1", "2025-2"):
                oferta.inscritos = min(oferta.cupo_maximo, 18 + oferta.materia.creditos * 2)
                oferta.save(update_fields=["inscritos"])
                for estudiante, estado in zip(estudiantes, (
                        Inscripcion.Estado.APROBADA, Inscripcion.Estado.APROBADA,
                        Inscripcion.Estado.CANCELADA)):
                    Inscripcion.objects.get_or_create(
                        estudiante=estudiante, oferta=oferta,
                        defaults={"estado": estado, "confirmada": timezone.now()})

        vigentes = [o for o in ofertas if o.periodo == "2026-1"]
        for oferta in vigentes[:3]:
            for estudiante in estudiantes[:2]:
                solicitud, creada = SolicitudCupo.objects.get_or_create(
                    oferta=oferta, estudiante=estudiante)
                if creada:
                    solicitud.procesar()
        # Demanda insatisfecha para el motor analítico
        saturada = vigentes[-1]
        saturada.cupo_maximo = 1
        saturada.inscritos = 1
        saturada.save(update_fields=["cupo_maximo", "inscritos"])
        for estudiante in estudiantes:
            solicitud, creada = SolicitudCupo.objects.get_or_create(
                oferta=saturada, estudiante=estudiante)
            if creada:
                solicitud.procesar()
        for oferta in vigentes[:4]:
            for estudiante in estudiantes[:1]:
                Inscripcion.objects.get_or_create(
                    estudiante=estudiante, oferta=oferta,
                    defaults={"estado": Inscripcion.Estado.ACTIVA})

    def _asistencia(self, usuarios, ofertas):
        sesiones = []
        for oferta in [o for o in ofertas if o.periodo == "2026-1"]:
            for i in range(6):
                sesion, _ = Sesion.objects.get_or_create(
                    oferta=oferta, fecha=date(2026, 2, 3) + timedelta(days=7 * i),
                    defaults={"tema": f"Unidad {i + 1}", "registrada": True})
                sesiones.append(sesion)
        # Estudiante con inasistencia crítica en la primera oferta
        criticas = [s for s in sesiones if s.oferta_id == ofertas[-5].pk][:4]
        if len(criticas) >= 3:
            for sesion in criticas[:3]:
                falta, creada = Falta.objects.get_or_create(
                    sesion=sesion, estudiante=usuarios["estudiante1"],
                    defaults={"motivo": "Inasistencia registrada en clase"})
                if creada:
                    falta.notificar()
            primera = Falta.objects.filter(estudiante=usuarios["estudiante1"]).first()
            if primera:
                primera.justificar("Cita médica con soporte adjunto.")
                falta = primera
                from evaluaciones.views import _recalcular_resumen
                _recalcular_resumen(falta)
        for oferta in [o for o in ofertas if o.periodo == "2026-1"]:
            for estudiante in (usuarios["estudiante2"], usuarios["estudiante3"]):
                resumen, _ = ResumenInasistencia.objects.get_or_create(
                    estudiante=estudiante, oferta=oferta)
                resumen.calcular()

    def _mensajes(self, usuarios, materias):
        hilo, creado = Hilo.objects.get_or_create(
            estudiante=usuarios["estudiante1"], docente=usuarios["docente1"],
            asunto="Duda sobre el taller de estructuras",
            defaults={"materia": materias[1], "tipo": Hilo.Tipo.ACADEMICO},
        )
        if creado:
            Mensaje.objects.create(
                hilo=hilo, autor=usuarios["estudiante1"],
                contenido="Buen día, ¿el taller se entrega en parejas o individual?",
            )
            Mensaje.objects.create(
                hilo=hilo, autor=usuarios["docente1"],
                contenido="Buen día. Se entrega en parejas y se sustenta en clase.",
                leido=True, leido_en=timezone.now(),
            )
        pendiente, creado2 = Hilo.objects.get_or_create(
            estudiante=usuarios["estudiante2"], docente=usuarios["docente2"],
            asunto="Solicitud de revisión de nota",
            defaults={"materia": materias[3], "tipo": Hilo.Tipo.ACADEMICO},
        )
        if creado2:
            Mensaje.objects.create(
                hilo=pendiente, autor=usuarios["estudiante2"],
                contenido="Solicito revisión de la nota del segundo parcial.",
            )

    def _quejas(self, usuarios, materias):
        categorias = [
            ("Académica", "Reclamos sobre contenidos, notas o metodología.",
             "Se revisará el caso con el docente y se enviará respuesta en 48 horas."),
            ("Administrativa", "Trámites, certificados y procesos de secretaría.",
             "El trámite se reactivará de inmediato desde secretaría académica."),
            ("Infraestructura", "Salones, laboratorios y equipos.",
             "Se programará la revisión del espacio o equipo reportado."),
            ("Tecnológica", "Plataforma, conectividad y servicios digitales.",
             "Soporte técnico validará el acceso y restablecerá el servicio."),
        ]
        objetos = {}
        for nombre, descripcion, solucion in categorias:
            categoria, _ = CategoriaQueja.objects.get_or_create(
                nombre=nombre, defaults={"descripcion": descripcion,
                                         "solucion_rapida": solucion})
            objetos[nombre] = categoria

        queja, creado = Queja.objects.get_or_create(
            asunto="Nota del parcial no publicada",
            radicada_por=usuarios["estudiante1"],
            defaults={"categoria": objetos["Académica"], "materia": materias[1],
                      "descripcion": "La nota del segundo parcial no aparece en el sistema.",
                      "prioridad": Queja.Prioridad.ALTA},
        )
        if creado:
            queja.asignar(usuarios["docente1"], "Se verifica con el docente de la asignatura.")
            queja.resolver(usuarios["docente1"], "Nota publicada y notificada al estudiante.")
        queja2, creado2 = Queja.objects.get_or_create(
            asunto="Falla de acceso a la plataforma de laboratorio",
            radicada_por=usuarios["estudiante2"],
            defaults={"categoria": objetos["Tecnológica"], "anonima": True,
                      "descripcion": "No puedo ingresar al laboratorio virtual desde ayer.",
                      "prioridad": Queja.Prioridad.MEDIA},
        )
        if creado2:
            queja2.estado = Queja.Estado.ABIERTO
            queja2.creada = timezone.now() - timedelta(days=6)
            queja2.save(update_fields=["estado", "creada"])
            queja2.escalar("Sin gestión oportuna; escalado al departamento (RN-10).")
        tercera, creado3 = Queja.objects.get_or_create(
            asunto="Solicitud de certificado académico",
            radicada_por=usuarios["estudiante3"],
            defaults={"categoria": objetos["Administrativa"], "materia": materias[2],
                      "descripcion": "Solicité certificado hace una semana y no hay respuesta.",
                      "prioridad": Queja.Prioridad.BAJA},
        )
        if creado3:
            tercera.asignar(usuarios["secretaria"], "Caso recibido por secretaría.")

    def _evaluacion(self, usuarios, materias, ofertas):
        hoy = timezone.localdate()
        periodo, creado = PeriodoEvaluacion.objects.get_or_create(
            nombre="Evaluación docente 2026-1",
            defaults={"fecha_inicio": hoy - timedelta(days=5),
                      "fecha_limite": hoy + timedelta(days=10), "activo": True,
                      "umbral_participacion": 50},
        )
        if creado:
            for estudiante in (usuarios["estudiante1"], usuarios["estudiante2"],
                               usuarios["estudiante3"]):
                for materia in materias[:3]:
                    for docente in materia.docentes.all():
                        InvitacionEvaluacion.objects.get_or_create(
                            periodo=periodo, estudiante=estudiante,
                            docente=docente, materia=materia)
        # Respuestas anónimas consolidadas (RN-05: mínimo 5 para publicar)
        if not RespuestaEvaluacion.objects.filter(periodo=periodo).exists():
            for materia, puntajes in ((materias[0], (4.6, 4.4, 4.8, 4.5, 4.7, 4.3)),
                                      (materias[1], (3.4, 3.6, 3.2, 3.5, 3.3)),
                                      (materias[2], (4.0, 4.2, 4.1, 3.9, 4.3))):
                for docente in materia.docentes.all():
                    for puntaje in puntajes:
                        RespuestaEvaluacion.objects.create(
                            periodo=periodo, docente=docente, materia=materia,
                            puntuacion=puntaje,
                            comentario="Comentario anónimo de ejemplo." if puntaje >= 4 else "",
                            respuestas_detalle={"p0": int(puntaje), "p1": int(puntaje)},
                        )

    def _plantillas(self):
        plantillas = [
            ("Ocupación de cupos por periodo", "OCUPACION",
             "Disponibilidad y tasa de ocupación de cada oferta."),
            ("Inasistencia por estudiante", "INASISTENCIA",
             "Porcentaje acumulado de inasistencia y nivel de riesgo."),
            ("Quejas y tiempos de respuesta", "QUEJAS",
             "Estado, gestor y horas hasta la resolución de cada caso."),
            ("Resultados de evaluación docente", "EVALUACION",
             "Promedios consolidados respetando el anonimato (RN-05)."),
            ("Trazabilidad de solicitudes de cupo", "SOLICITUDES",
             "Estado y prioridad de cada solicitud procesada."),
            ("Mensajería y tiempos de respuesta", "MENSAJERIA",
             "Hilos abiertos, tiempos sin respuesta y cierres."),
            ("Resumen académico por estudiante", "ACADEMICO",
             "Promedio, semestre y materias activas por estudiante."),
        ]
        for nombre, tipo, descripcion in plantillas:
            PlantillaReporte.objects.get_or_create(
                nombre=nombre, defaults={"tipo": tipo, "descripcion": descripcion})





