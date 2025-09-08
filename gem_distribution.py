bl_info = {
    "name": "Distribuir Gemas Panal (Activo al Centro)",
    "author": "Oscar Fernando",
    "version": (1, 9),
    "blender": (3, 6, 0),
    "location": "View3D > N Panel > Joyería",
    "description": "Distribuye gemas en patrón de panal tomando el objeto activo como centro, con slider normalizado (0–1)",
    "category": "Object",
}

import bpy
import math


def rango_por_escala(scale_x):
    """Devuelve rango min/max de separación según escala X"""
    base_min, base_max = 1.156, 1.204
    factor = round((scale_x - 1.0) * 10)  # -1 si 0.9, 0 si 1.0, +1 si 1.1
    min_val = base_min + factor * 0.100
    max_val = base_max + factor * 0.100
    return min_val, max_val


def calcular_distancia(scale_x, slider_val):
    """Convierte el valor del slider (0–1) en mm reales según escala"""
    min_val, max_val = rango_por_escala(scale_x)
    return min_val + (max_val - min_val) * slider_val


class OBJECT_OT_distribuir_gemas_panal_centro(bpy.types.Operator):
    bl_idname = "object.distribuir_gemas_panal_centro"
    bl_label = "Distribuir Panal (Centro Activo)"
    bl_description = "Distribuye las gemas en patrón de panal tomando el objeto activo como centro"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        seleccionados = context.selected_objects
        activo = context.active_object
        
        if not seleccionados or not activo:
            self.report({"WARNING"}, "Debes tener objetos seleccionados y un activo")
            return {"CANCELLED"}
        
        # calcular distancia real en mm según slider y escala
        slider_val = context.scene.gema_spacing_slider
        distancia = calcular_distancia(activo.scale.x, slider_val)
        
        # parámetros panal
        offset_x = distancia / 2
        offset_y = distancia * math.sqrt(3) / 2
        
        # referencia: el activo es el centro
        x_base, y_base, z_base = activo.location
        
        # quitamos el activo de la lista
        otros = [obj for obj in seleccionados if obj != activo]
        
        # estimamos tamaño del bloque hexagonal
        total = len(seleccionados)
        filas = int(math.ceil(math.sqrt(total)))
        
        idx = 0
        for fila in range(-filas//2, filas//2 + 1):
            for col in range(-filas//2, filas//2 + 1):
                if idx >= len(otros):
                    break
                
                if fila == 0 and col == 0:  # saltar el centro
                    continue
                
                x = x_base + col * distancia + (offset_x if fila % 2 else 0)
                y = y_base + fila * offset_y
                z = z_base
                
                otros[idx].location = (x, y, z)
                idx += 1
        
        self.report({"INFO"}, f"Usando distancia: {distancia:.3f} mm")
        return {"FINISHED"}


class VIEW3D_PT_distribuir_gemas_panel(bpy.types.Panel):
    bl_label = "Distribuir Gemas"
    bl_idname = "VIEW3D_PT_distribuir_gemas_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Joyería"
    
    def draw(self, context):
        layout = self.layout
        activo = context.active_object

        if activo:
            min_val, max_val = rango_por_escala(activo.scale.x)
            slider_val = context.scene.gema_spacing_slider
            distancia_real = calcular_distancia(activo.scale.x, slider_val)
            
            layout.label(text=f"Escala X: {activo.scale.x:.2f}")
            layout.prop(context.scene, "gema_spacing_slider", slider=True, text="Distancia (0–1)")
            layout.label(text=f"Distancia real: {distancia_real:.3f} mm")
            layout.label(text=f"Rango válido: {min_val:.3f} mm - {max_val:.3f} mm")
        else:
            layout.label(text="Selecciona un objeto activo")
        
        layout.operator("object.distribuir_gemas_panal_centro")


def register():
    bpy.utils.register_class(OBJECT_OT_distribuir_gemas_panal_centro)
    bpy.utils.register_class(VIEW3D_PT_distribuir_gemas_panel)
    
    bpy.types.Scene.gema_spacing_slider = bpy.props.FloatProperty(
        name="Distancia (0–1)",
        description="Valor normalizado para calcular la separación",
        default=0.0,  # empieza en el mínimo
        min=0.0,
        max=1.0,
        step=0.01,
        precision=3
    )


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_distribuir_gemas_panal_centro)
    bpy.utils.unregister_class(VIEW3D_PT_distribuir_gemas_panel)
    del bpy.types.Scene.gema_spacing_slider


if __name__ == "__main__":
    register()
