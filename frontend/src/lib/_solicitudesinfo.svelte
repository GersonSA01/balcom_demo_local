<script>
  import { Carousel, CarouselItem } from "sveltestrap";

  // ✅ DATA QUEMADA (simulada)
  const eSolicitudes = {
    en_tramite: [
      {
        nombre_servicio_minus: "Servicio médico",
        fecha_creacion_v2: "2025-12-16",
        hora_creacion_v2: "10:42",
      },
      {
        nombre_servicio_minus: "Beca estudiantil",
        fecha_creacion_v2: "2025-12-15",
        hora_creacion_v2: "19:05",
      },
    ],
    pendiente: [
      {
        nombre_servicio_minus: "Servicio psicológico",
        fecha_creacion_v2: "2025-12-14",
        hora_creacion_v2: "09:18",
      },
    ],
    aprobado: [
      {
        nombre_servicio_minus: "Cobertura seguro estudiantil",
        fecha_creacion_v2: "2025-12-10",
        hora_creacion_v2: "14:22",
      },
    ],
    corregir: [],
    rechazado: [],
  };

  // Carruseles (índices activos)
  let activeItemTramite = 0;
  let activeItemPendiente = 0;
  let activeItemAprobado = 0;
  let activeItemCorregir = 0;
  let activeItemRechazado = 0;

  const hasAny =
    (eSolicitudes.en_tramite?.length ?? 0) +
      (eSolicitudes.pendiente?.length ?? 0) +
      (eSolicitudes.aprobado?.length ?? 0) +
      (eSolicitudes.corregir?.length ?? 0) +
      (eSolicitudes.rechazado?.length ?? 0) >
    0;

  const changeItem = (tipo, index) => {
    if (tipo === "T") activeItemTramite = index;
    if (tipo === "P") activeItemPendiente = index;
    if (tipo === "A") activeItemAprobado = index;
    if (tipo === "C") activeItemCorregir = index;
    if (tipo === "R") activeItemRechazado = index;
  };
</script>

<div class="panel">
  <h5 class="solicitud-title">{hasAny ? "Solicitudes (Quemadas por el momento)" : "Estado de mis solicitudes"}</h5>

  <div class="solicitudes-container {hasAny ? "" : "container-empty"}">
    {#if hasAny}
      {#if eSolicitudes.en_tramite?.length}
        <h4>Solicitudes en Trámite</h4>
        <Carousel activeIndex={activeItemTramite} dark>
          <ol class="carousel-indicators">
            {#each eSolicitudes.en_tramite as _, i}
              <li
                class:active={activeItemTramite === i}
                on:click={() => changeItem("T", i)}
              />
            {/each}
          </ol>

          <div class="carousel-inner">
            {#each eSolicitudes.en_tramite as solicitud, i}
              <CarouselItem>
                <div class="card card-hover {activeItemTramite === i ? "d-block" : "d-none"}">
                  <h6 class="solicitud-titulo">{solicitud.nombre_servicio_minus}</h6>
                  <hr />
                  <p>
                    Ingresada el <strong>{solicitud.fecha_creacion_v2}</strong> a las
                    <strong>{solicitud.hora_creacion_v2}</strong> y se encuentra en
                    <strong>revisión interna</strong>.
                  </p>
                </div>
              </CarouselItem>
            {/each}
          </div>
        </Carousel>
      {/if}

      {#if eSolicitudes.pendiente?.length}
        <h4>Solicitudes Pendientes</h4>
        <Carousel activeIndex={activeItemPendiente} dark>
          <ol class="carousel-indicators">
            {#each eSolicitudes.pendiente as _, i}
              <li
                class:active={activeItemPendiente === i}
                on:click={() => changeItem("P", i)}
              />
            {/each}
          </ol>

          <div class="carousel-inner">
            {#each eSolicitudes.pendiente as solicitud, i}
              <CarouselItem>
                <div class="card card-hover {activeItemPendiente === i ? "d-block" : "d-none"}">
                  <h6 class="solicitud-titulo">{solicitud.nombre_servicio_minus}</h6>
                  <hr />
                  <p>
                    Ingresada el <strong>{solicitud.fecha_creacion_v2}</strong> a las
                    <strong>{solicitud.hora_creacion_v2}</strong> y está en
                    <strong>pendiente</strong>.
                  </p>
                </div>
              </CarouselItem>
            {/each}
          </div>
        </Carousel>
      {/if}

      {#if eSolicitudes.aprobado?.length}
        <h4>Solicitudes Aprobadas</h4>
        <Carousel activeIndex={activeItemAprobado} dark>
          <ol class="carousel-indicators">
            {#each eSolicitudes.aprobado as _, i}
              <li
                class:active={activeItemAprobado === i}
                on:click={() => changeItem("A", i)}
              />
            {/each}
          </ol>

          <div class="carousel-inner">
            {#each eSolicitudes.aprobado as solicitud, i}
              <CarouselItem>
                <div class="card card-hover {activeItemAprobado === i ? "d-block" : "d-none"}">
                  <h6 class="solicitud-titulo">{solicitud.nombre_servicio_minus}</h6>
                  <hr />
                  <p>
                    Ingresada el <strong>{solicitud.fecha_creacion_v2}</strong> a las
                    <strong>{solicitud.hora_creacion_v2}</strong> y está
                    <strong>aprobada</strong>.
                  </p>
                </div>
              </CarouselItem>
            {/each}
          </div>
        </Carousel>
      {/if}
    {:else}
      <p class="solicitudes-empty-text">Usted no posee actualmente ninguna solicitud</p>
    {/if}
  </div>

  {#if hasAny}
    <a href="#" class="btn-missolicitudes">Ver mis solicitudes</a>
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
  }

  .btn-missolicitudes {
    display: block;
    text-align: center;
    border-radius: 14px;
    background-color: #12216a;
    padding: 10px 12px;
    color: #fff;
    font-weight: 600;
  }
  .btn-missolicitudes:hover {
    background-color: #0a4985;
  }

  .solicitud-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: #12216a;
    text-align: center;
    margin: 0;
  }

  .solicitudes-container {
    background-color: #e8effb;
    padding: 10px;
    border-radius: 14px;
    border: 1px solid #d9e3f5;
    position: relative;
    flex: 1;
    overflow: auto;
  }

  .container-empty {
    background-color: #fff;
    border: 2px dotted #707070;
    display: grid;
    place-items: center;
    min-height: 220px;
  }

  h4 {
    font-weight: 800;
    margin: 10px 0 6px;
    color: #253ca6;
    font-size: 0.95rem;
    text-align: center;
  }

  .card-hover {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 14px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
    margin: 8px 4px 18px;
  }

  .solicitud-titulo {
    font-size: 0.95rem;
    font-weight: 700;
    color: #12216a;
    margin: 0;
  }

  p {
    font-size: 0.86rem;
    color: #60606a;
    margin: 0;
  }

  .carousel-indicators {
    position: absolute;
    bottom: 6px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 8px;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .carousel-indicators li {
    background-color: #d3dbe3;
    border-radius: 50%;
    width: 8px;
    height: 8px;
    cursor: pointer;
  }

  .carousel-indicators li.active {
    background-color: #0a4985;
  }

  .solicitudes-empty-text {
    font-size: 0.9rem;
    color: #707070;
    text-align: center;
    margin: 0;
  }
</style>
