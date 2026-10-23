"""Pruebas de aceptación: el flujo completo tal como lo usan las personas."""

import re


def html(respuesta):
    return respuesta.get_data(as_text=True)


def test_flujo_completo_desde_el_portal_hasta_el_cierre(cliente):
    # 1. Una docente registra el problema en el portal.
    respuesta = cliente.post(
        "/portal",
        data={
            "solicitante": "Laura Gómez",
            "categoria": "hardware",
            "prioridad": "media",
            "descripcion": "El proyector del aula 204 no enciende.",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    pagina = html(respuesta)
    assert "Su solicitud fue registrada" in pagina
    codigo = re.search(r"SOL-\d{8}-[0-9A-F]{6}", pagina).group()

    # 2. Consulta con el código (en minúsculas y con espacios).
    respuesta = cliente.get("/portal", query_string={"codigo": f" {codigo.lower()} "})
    assert respuesta.status_code == 200
    assert 'data-estado="registrada"' in html(respuesta)

    # 3. Soporte asigna un técnico.
    respuesta = cliente.post(
        f"/soporte/{codigo}/tecnico", data={"tecnico": "Carlos Ruiz"}, follow_redirects=True
    )
    assert respuesta.status_code == 200
    assert 'data-estado="asignada"' in html(respuesta)

    # 4. y 5. Pasa a en_proceso y luego a resuelta.
    for estado in ("en_proceso", "resuelta"):
        respuesta = cliente.post(
            f"/soporte/{codigo}/estado", data={"estado": estado}, follow_redirects=True
        )
        assert respuesta.status_code == 200
        assert "El estado de la solicitud se actualizó." in html(respuesta)

    # 6. Intentar cerrar sin comentario muestra un error claro.
    respuesta = cliente.post(
        f"/soporte/{codigo}/estado", data={"estado": "cerrada", "comentario": ""}
    )
    assert respuesta.status_code == 400
    assert (
        "Para cerrar la solicitud escriba un comentario que explique cómo se resolvió."
        in html(respuesta)
    )

    # 7. Cerrar con comentario.
    respuesta = cliente.post(
        f"/soporte/{codigo}/estado",
        data={"estado": "cerrada", "comentario": "Se cambió la lámpara del proyector."},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200

    # 8. El portal muestra "cerrada", el técnico y el historial con los 5 estados.
    pagina = html(cliente.get("/portal", query_string={"codigo": codigo}))
    datos = pagina.split('<ol class="historial">')[0]
    assert re.search(r'<dt>Estado</dt><dd><span class="estado" data-estado="cerrada">', datos)
    assert "Carlos Ruiz" in datos

    historial = cliente.get(f"/api/solicitudes/{codigo}").get_json()["historial"]
    assert [h["estado_nuevo"] for h in historial] == [
        "registrada",
        "asignada",
        "en_proceso",
        "resuelta",
        "cerrada",
    ]
    assert "Se cambió la lámpara del proyector." in pagina


def test_portal_muestra_errores_y_conserva_lo_escrito(cliente):
    respuesta = cliente.post(
        "/portal",
        data={"solicitante": "Pedro", "categoria": "redes", "descripcion": "Sin red"},
    )
    assert respuesta.status_code == 400
    pagina = html(respuesta)
    assert "La descripción es muy corta" in pagina
    assert "Falta la prioridad; es un campo obligatorio." in pagina
    assert 'value="Pedro"' in pagina
    assert '<option value="redes" selected>' in pagina
    assert ">Sin red</textarea>" in pagina


def test_portal_no_muestra_acciones_de_soporte_y_el_panel_si(cliente, servicio_app):
    codigo = servicio_app.registrar(
        {
            "solicitante": "Ana",
            "categoria": "software",
            "prioridad": "baja",
            "descripcion": "No abre el sistema de notas.",
        }
    )["codigo"]

    portal = html(cliente.get("/portal", query_string={"codigo": codigo}))
    assert codigo in portal
    assert "Avance de la solicitud" in portal
    assert "Asignar técnico" not in portal
    assert "Cambiar estado" not in portal
    assert 'action="/soporte' not in portal

    panel = html(cliente.get(f"/soporte/{codigo}"))
    assert "Asignar técnico" in panel
    assert "Cambiar estado" in panel
    assert f'action="/soporte/{codigo}/tecnico"' in panel
    assert f'action="/soporte/{codigo}/estado"' in panel
    # Solo se ofrecen los estados permitidos desde "registrada".
    opciones = re.findall(r'<option value="(\w+)"', panel.split('id="estado"')[1])
    assert opciones == ["asignada", "cancelada"]
    assert "Avance de la solicitud" in panel


def test_panel_lista_filtra_y_busca(cliente, servicio_app):
    base = {"solicitante": "Ana", "categoria": "otro", "prioridad": "baja",
            "descripcion": "Necesito ayuda con el correo."}
    primera = servicio_app.registrar(base)["codigo"]
    segunda = servicio_app.registrar(base)["codigo"]
    servicio_app.asignar_tecnico(segunda, "Luis")

    listado = html(cliente.get("/soporte"))
    assert primera in listado and segunda in listado

    filtrado = html(cliente.get("/soporte", query_string={"estado": "asignada"}))
    assert segunda in filtrado and primera not in filtrado

    buscado = html(cliente.get("/soporte", query_string={"codigo": primera.lower()}))
    assert primera in buscado and segunda not in buscado
