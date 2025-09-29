bl_info = {
    "name": "Exportar STL Simplificado (Prongs, Cutter, Numéricos y Curvas)",
    "author": "Oscar Fernando",
    "version": (2, 0),
    "blender": (3, 6, 0),
    "location": "View3D > N Panel > Export STL",
    "description": "Exporta Prongs, Cutter, objetos numéricos y curvas con geometría en STLs, agrupando variantes con mismo nombre base",
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

# --- Función auxiliar: obtener malla desde mesh o curva ---
def collect_mesh_objects(objs):
    """Devuelve una lista de objetos malla. Convierte curvas temporalmente a mesh."""
    mesh_objs = []
    temp_objs = []

    for obj in objs:
        if obj.type == "MESH":
            mesh_objs.append(obj)
        elif obj.type == "CURVE":
            # Duplicar y convertir a mesh para no modificar el original
            dup = obj.copy()
            dup.data = obj.data.copy()
            bpy.context.collection.objects.link(dup)
            bpy.context.view_layer.objects.active = dup
            bpy.ops.object.select_all(action='DESELECT')
            dup.select_set(True)
            bpy.ops.object.convert(target='MESH')
            mesh_objs.append(dup)
            temp_objs.append(dup)

    return mesh_objs, temp_objs

# --- Operador Exportar ---
class EXPORTSTL_OT_export(bpy.types.Operator):
    bl_idname = "exportstl.export"
    bl_label = "Exportar STL"
    bl_description = "Exporta Prongs, Cutter, objetos numéricos y curvas con geometría agrupando por nombre base"

    def execute(self, context):
        props = context.scene.export_stl_props
        export_folder = bpy.path.abspath(props.export_path)

        if not os.path.exists(export_folder):
            os.makedirs(export_folder)

        # --- Desocultar todos los objetos ---
        bpy.ops.object.hide_view_clear()

        temp_to_delete = []

        # --- Exportar grupos Prongs y Cutter ---
        grupos = {
            "Prongs": [obj for obj in context.view_layer.objects if obj.name.startswith("Prongs")],
            "Cutter": [obj for obj in context.view_layer.objects if obj.name.startswith("Cutter")],
        }

        for nombre, objetos in grupos.items():
            if objetos:
                bpy.ops.object.select_all(action='DESELECT')
                mesh_objs, temps = collect_mesh_objects(objetos)
                temp_to_delete.extend(temps)

                for obj in mesh_objs:
                    obj.select_set(True)
                context.view_layer.objects.active = mesh_objs[0]

                filepath = os.path.join(export_folder, f"{nombre}.stl")
                bpy.ops.export_mesh.stl(
                    filepath=filepath,
                    use_selection=True,
                    ascii=False,
                    use_mesh_modifiers=True
                )
                self.report({'INFO'}, f"{nombre} exportado a {filepath}")

        # --- Exportar objetos que empiezan con un número ---
        regex_num = re.compile(r"^\d")
        objetos_numericos = [obj for obj in context.view_layer.objects if regex_num.match(obj.name)]

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
            mesh_objs, temps = collect_mesh_objects(objetos)
            temp_to_delete.extend(temps)

            for obj in mesh_objs:
                obj.select_set(True)
            context.view_layer.objects.active = mesh_objs[0]

            filepath = os.path.join(export_folder, f"{base_name}.stl")
            bpy.ops.export_mesh.stl(
                filepath=filepath,
                use_selection=True,
                ascii=False,
                use_mesh_modifiers=True
            )
            self.report({'INFO'}, f"{base_name} exportado a {filepath}")

        # --- Eliminar duplicados temporales ---
        bpy.ops.object.select_all(action='DESELECT')
        for obj in temp_to_delete:
            obj.select_set(True)
        bpy.ops.object.delete()

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
