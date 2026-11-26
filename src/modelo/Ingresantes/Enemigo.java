package modelo.Ingresantes;

import java.util.ArrayList;

import modelo.TipoCiudad;
import modelo.TipoClan;
import modelo.TipoIngresante;
import modelo.TipoRaza;
import modelo.documentos.Documento;

public class Enemigo extends Ingresante{

    private boolean portaBomba;

    public Enemigo(String nombreDeclarado, ArrayList<Documento> documentos, TipoIngresante tipo, TipoRaza raza, TipoClan clan, TipoCiudad ciudad, String rutaImagen, String motivoVisita, boolean portaBomba){
        super(nombreDeclarado, documentos, tipo, raza, clan, ciudad, rutaImagen, motivoVisita);
        this.portaBomba = portaBomba;
    }

    public boolean isPortaBomba(){
        return this.portaBomba;
    }

    // Un enemigo que lleva una bomba se muestra nervioso: es una pista sutil para el jugador.
    @Override
    public String darPresentacion(){
        if (this.portaBomba) {
            return "(Suda y mira hacia los costados) Buenos días, vengo a ingresar al planeta.";
        }
        return "Buenos días, vengo a ingresar al planeta.";
    }

    @Override
    public boolean esAmenaza() {
        return true;
    }
}