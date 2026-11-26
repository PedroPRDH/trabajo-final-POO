package modelo.Ingresantes;
import java.util.ArrayList;

import modelo.TipoCiudad;
import modelo.TipoClan;
import modelo.TipoIngresante;
import modelo.TipoRaza;
import modelo.documentos.Documento;

public class IngresanteRegular extends Ingresante{
    
    
    public IngresanteRegular(String nombreDeclarado, ArrayList<Documento> documentos, TipoIngresante tipo, TipoRaza raza, TipoClan clan, TipoCiudad ciudad, String rutaImagen, String motivoVisita){
        super(nombreDeclarado, documentos, tipo, raza, clan, ciudad, rutaImagen, motivoVisita);
    
    }


@Override 
    public String darPresentacion(){
        // Texto neutro: no debe delatar si el ingresante es o no una amenaza.
        return "Buenos días, vengo a ingresar al planeta.";
    }

@Override // METODO ABSTRACTO: que devuelve true o false si el ingresante es una amenaza
public boolean esAmenaza() {
    return false;
}

}
