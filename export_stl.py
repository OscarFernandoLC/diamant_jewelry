bl_info = {
    "name": "Exportar STL Simplificado (Prongs, Cutter y Numéricos Agrupados)",
    "author": "Oscar Fernando",
    "version": (1, 9),
    "blender": (3, 6, 0),
    "location": "View3D > N Panel > Export STL",
    "description": "Exporta Prongs y Cutter agrupados + objetos numéricos en STLs, agrupando variantes con mismo nombre base",
    "category": "Import-Export",
}

import bpy
import os
import re

# --- Propiedades ---
class ExportSTLProps(bpy.types.PropertyGroup):
    export_path: bpy.props.StringProperty(
        name="Carpeta de exportación",
        subtype="DIR_PATH",
        default="//stl_exports/"
    )

# --- Operador Exportar ---
class EXPORTSTL_OT_export(bpy.types.Operator):
    bl_idname = "exportstl.export"
    bl_label = "Exportar STL"
    bl_description = "Exporta Prongs, Cutter y objetos con nombres que empiezan en número agrupando por nombre base"

    def execute(self, context):
        props = context.scene.export_stl_props
        export_folder = bpy.path.abspath(props.export_path)

        if not os.path.exists(export_folder):
            os.makedirs(export_folder)

        # --- Desocultar todos los objetos (equivalente a Alt+H) ---
        bpy.ops.object.hide_view_clear()

        # --- Exportar grupos Prongs y Cutter ---
        grupos = {
            "Prongs": [obj for obj in context.view_layer.objects if obj.type == "MESH" and obj.name.startswith("Prongs")],
            "Cutter": [obj for obj in context.view_layer.objects if obj.type == "MESH" and obj.name.startswith("Cutter")],
        }

        for nombre, objetos in grupos.items():
            if objetos:
                bpy.ops.object.select_all(action='DESELECT')
                for obj in objetos:
                    obj.select_set(True)
                context.view_layer.objects.active = objetos[0]

                filepath = os.path.join(export_folder, f"{nombre}.stl")
                bpy.ops.export_mesh.stl(
                    filepath=filepath,
                    use_selection=True,
                    ascii=False,
                    use_mesh_modifiers=True
                )
                self.report({'INFO'}, f"{nombre} exportado a {filepath}")

        # --- Exportar objetos que empiezan con un número agrupados por nombre base ---
        regex_num = re.compile(r"^\d")
        objetos_numericos = [obj for obj in context.view_layer.objects if obj.type == "MESH" and regex_num.match(obj.name)]

        # Agrupar por nombre base (quitamos sufijos .001, .002, etc.)
        grupos_numericos = {}
        for obj in objetos_numericos:
            base_name = obj.name.split(".")[0]
            if base_name not in grupos_numericos:
                grupos_numericos[base_name] = []
            grupos_numericos[base_name].append(obj)

        # Exportar cada grupo como un STL único
        for base_name, objetos in grupos_numericos.items():
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objetos:
                obj.select_set(True)
            context.view_layer.objects.active = objetos[0]

            filepath = os.path.join(export_folder, f"{base_name}.stl")
            bpy.ops.export_mesh.stl(
                filepath=filepath,
                use_selection=True,
                ascii=False,
                use_mesh_modifiers=True
            )
            self.report({'INFO'}, f"{base_name} exportado a {filepath}")

        return {'FINISHED'}

# --- UI ---
class EXPORTSTL_PT_panel(bpy.types.Panel):
    bl_label = "Export STL Simplificado"
    bl_idname = "EXPORTSTL_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Export STL"

    def draw(self, context):
        layout = self.layout
        props = context.scene.export_stl_props

        layout.prop(props, "export_path")
        layout.separator()
        layout.operator("exportstl.export", icon="EXPORT")

# --- Registro ---
classes = [
    ExportSTLProps,
    EXPORTSTL_OT_export,
    EXPORTSTL_PT_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.export_stl_props = bpy.props.PointerProperty(type=ExportSTLProps)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.export_stl_props

if __name__ == "__main__":
    register()
