package modelo.politicas;

import modelo.Ingresantes.Ingresante;

/**
 * Contrato de una regla fronteriza: toda política debe poder verificar a un
 * ingresante y explicar por qué lo rechaza. No tiene estado ni lógica común,
 * por eso es una interfaz y no una clase abstracta.
 */
public interface PoliticaFronteriza {

    boolean esValido(Ingresante ingresante);

    String getMotivoRechazo();
}
