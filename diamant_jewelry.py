bl_info = {
    "name": "Jewelry Tools ",
    "author": "Oscar Fernando",
    "version": (1, 3, 0),
    "blender": (3, 6, 0),
    "location": "View3D > N Panel > Jewelry Tools",
    "description": "Herramientas para creación de joyerías.",
    "category": "Object",
}

import bpy
import mathutils
from bpy.props import (
    BoolProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
)
from mathutils import Vector


# ------------------------------
# Utilidades
# ------------------------------

def get_dir_world(obj, mode: str) -> Vector:
    """Devuelve la dirección de proyección en espacio mundo."""
    if mode == 'GLOBAL_Z_DOWN':
        return Vector((0, 0, -1))
    elif mode == 'LOCAL_Z_NEG':
        # -Z local del objeto (mover como presionar Z con orientación local)
        return -(obj.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    else:
        return Vector((0, 0, -1))

def raycast_object_world(eval_target_obj, start_world: Vector, dir_world: Vector):
    """
    Lanza un raycast contra eval_target_obj (evaluated) convirtiendo
    a espacio local del objetivo (requerido por Blender 3.6).
    Devuelve (success, hit_world, normal_world, face_index).
    """
    mat = eval_target_obj.matrix_world
    imat = mat.inverted()

    start_local = imat @ start_world
    end_local = imat @ (start_world + dir_world)
    dir_local = (end_local - start_local).normalized()

    success, loc_local, nrm_local, face_index = eval_target_obj.ray_cast(start_local, dir_local)
    if not success:
        return False, None, None, -1

    hit_world = mat @ loc_local
    normal_world = (mat.to_3x3() @ nrm_local).normalized()
    return True, hit_world, normal_world, face_index



#Mover 1 en Z
# Propiedades para el contador
def register_props():
    bpy.types.Scene.z_up_count = bpy.props.IntProperty(
        name="Subidas", default=0
    )
    bpy.types.Scene.z_down_count = bpy.props.IntProperty(
        name="Bajadas", default=0
    )


def unregister_props():
    del bpy.types.Scene.z_up_count
    del bpy.types.Scene.z_down_count




# ------------------------------
# Propiedades
# ------------------------------

class SNAPZ_Props(bpy.types.PropertyGroup):
    target: PointerProperty(
        name="Malla objetivo",
        type=bpy.types.Object,
        description="Malla sobre la que se pegarán los objetos (si está vacío, se usa el activo)",
    )
    direction: EnumProperty(
        name="Dirección",
        description="Dirección a lo largo de la que se proyecta",
        items=[
            ('LOCAL_Z_NEG', "Z local (−Z)", "Proyectar a lo largo de la Z local del objeto"),
            ('GLOBAL_Z_DOWN', "Z global (−Z)", "Proyectar a lo largo de la Z global"),
        ],
        default='LOCAL_Z_NEG',
    )
    align_rotation: BoolProperty(
        name="Alinear rotación a la normal",
        description="Hace que el eje Z del objeto apunte a la normal donde cae (similar a Align Rotation to Target)",
        default=True,
    )
    offset: FloatProperty(
        name="Offset",
        description="Separación a lo largo de la normal (positivo despega un poco)",
        default=0.0,
        min=-1000.0, max=1000.0,
        step=0.1, precision=4,
    )
    backtrack: FloatProperty(
        name="Retroceso de inicio",
        description="Cuánto retroceder desde el origen del objeto en dirección CONTRARIA antes de lanzar el rayo (para asegurar cruce)",
        default=0.1,
        min=0.0, max=1000.0,
        step=0.1, precision=3,
    )
    max_step: FloatProperty(
        name="Paso de rayo",
        description="Magnitud del vector de rayo (no es distancia real, pero ayuda a la estabilidad del cálculo)",
        default=10000.0,
        min=0.01, max=1e9,
    )

# ------------------------------
# Operador
# ------------------------------

class OBJECT_OT_snap_in_z(bpy.types.Operator):
    bl_idname = "object.snap_in_z"
    bl_label = "Pegar en Z"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        props = scn.snapz_props

        # Determinar objetivo
        target = props.target if props.target else context.active_object
        if not target or target.type != 'MESH':
            self.report({'ERROR'}, "Debes tener una malla objetivo (activa o seleccionada en el panel).")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        eval_target = target.evaluated_get(depsgraph)

        # Objetos a pegar (excluye la malla objetivo)
        sel_objs = [o for o in context.selected_objects if o != target]

        if not sel_objs:
            self.report({'WARNING'}, "No hay objetos seleccionados (aparte del objetivo).")
            return {'CANCELLED'}

        moved = 0
        for obj in sel_objs:
            dir_world = get_dir_world(obj, props.direction)
            if dir_world.length == 0.0:
                continue

            # Punto de inicio: un poco "detrás" del objeto (contrario a la dirección), para garantizar cruce
            start_world = obj.location - dir_world.normalized() * props.backtrack

            # Lanza raycast (en 3.6 convertimos el rayo a espacio local del target)
            # Usamos un vector largo para que el rayo recorra "bastante".
            success, hit_world, normal_world, _ = raycast_object_world(
                eval_target,
                start_world,
                dir_world.normalized() * props.max_step
            )

            if not success:
                # Si no pega, intenta en sentido contrario (por seguridad)
                success, hit_world, normal_world, _ = raycast_object_world(
                    eval_target,
                    start_world,
                    (-dir_world).normalized() * props.max_step
                )

            if success:
                # Nueva ubicación (con offset sobre la normal si se desea)
                new_loc = hit_world + normal_world * props.offset
                obj.location = new_loc

                if props.align_rotation:
                    # Alinear Z del objeto a la normal del impacto (similar a Align Rotation to Target)
                    quat = normal_world.to_track_quat('Z', 'Y')
                    obj.rotation_euler = quat.to_euler(obj.rotation_mode)

                moved += 1

        if moved == 0:
            self.report({'WARNING'}, "No se encontró intersección para los objetos seleccionados. Revisa dirección u objetivo.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Pegados {moved} objeto(s) a '{target.name}'.")
        return {'FINISHED'}

# ------------------------------
# Operador aplicar transform + limpiar constraints
# ------------------------------

class OBJECT_OT_apply_and_clear_constraints(bpy.types.Operator):
    bl_idname = "object.apply_and_clear_constraints"
    bl_label = "Aplicar Visual y Limpiar Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sel_objs = context.selected_objects
        if not sel_objs:
            self.report({'WARNING'}, "No hay objetos seleccionados.")
            return {'CANCELLED'}

        for obj in sel_objs:
            # Activa el objeto para aplicar
            context.view_layer.objects.active = obj

            # Aplica transformaciones visuales
            bpy.ops.object.visual_transform_apply()

            # Limpia constraints
            bpy.ops.object.constraints_clear()

        self.report({'INFO'}, f"Aplicadas y limpiadas constraints en {len(sel_objs)} objeto(s).")
        return {'FINISHED'}


#EdgeLoop
class MESH_OT_separar_loop_shrinkwrap(bpy.types.Operator):
    """Separa el loop seleccionado como objetos nuevos (Loose Parts) y añade Shrinkwrap"""
    bl_idname = "mesh.separar_loop_shrinkwrap_only"
    bl_label = "Loop → Shrinkwrap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Selecciona un objeto de tipo malla")
            return {'CANCELLED'}

        # Cambiar a Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')

        # Duplicar selección
        bpy.ops.mesh.duplicate()

        # Separar en partes sueltas (cada isla de edges será un objeto)
        bpy.ops.mesh.separate(type='LOOSE')

        # Volver a modo objeto
        bpy.ops.object.mode_set(mode='OBJECT')

        # Obtener los objetos resultantes
        sel_objs = context.selected_objects
        new_objs = [o for o in sel_objs if o != obj]

        if not new_objs:
            self.report({'ERROR'}, "No se pudo separar el loop")
            return {'CANCELLED'}

        # Agregar Shrinkwrap a cada nuevo objeto
        for new_obj in new_objs:
            shrinkwrap = new_obj.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
            shrinkwrap.target = obj
            shrinkwrap.wrap_method = 'NEAREST_SURFACEPOINT'

        # Deseleccionar todo y dejar seleccionados solo los nuevos objetos
        bpy.ops.object.select_all(action='DESELECT')
        for new_obj in new_objs:
            new_obj.select_set(True)
        context.view_layer.objects.active = new_objs[0]

        self.report({'INFO'}, f"{len(new_objs)} loops separados como objetos con Shrinkwrap hacia '{obj.name}'")
        return {'FINISHED'}

class OBJECT_OT_convert_to_curve(bpy.types.Operator):
    """Convierte los objetos seleccionados en curvas y los organiza en la colección 'Curves'"""
    bl_idname = "object.convert_to_curve"
    bl_label = "Convertir a Curva"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sel_objs = context.selected_objects
        if not sel_objs:
            self.report({'ERROR'}, "No hay objetos seleccionados")
            return {'CANCELLED'}

        # Buscar colección "Curves" en la escena activa
        curves_collection = None
        for coll in context.scene.collection.children:
            if coll.name == "Curves":
                curves_collection = coll
                break

        # Si no existe, crearla en la escena actual
        if not curves_collection:
            curves_collection = bpy.data.collections.new("Curves")
            context.scene.collection.children.link(curves_collection)

        converted = []

        for obj in sel_objs:
            obj_name = obj.name

            # Hacer activo para convertir
            context.view_layer.objects.active = obj

            # Convertir a curva
            bpy.ops.object.convert(target='CURVE')

            # Obtener el objeto convertido (sigue con el mismo nombre)
            obj_curve = bpy.data.objects.get(obj_name)
            if obj_curve:
                obj_curve.show_in_front = True
                converted.append(obj_curve)

                # Mover a colección "Curves" de la escena activa
                # 1. Quitar de las colecciones actuales
                for coll in obj_curve.users_collection:
                    coll.objects.unlink(obj_curve)
                # 2. Agregar a "Curves"
                curves_collection.objects.link(obj_curve)

        if converted:
            self.report({'INFO'}, f"{len(converted)} objeto(s) convertidos a curva y movidos a 'Curves'")
        else:
            self.report({'WARNING'}, "No se pudieron convertir los objetos seleccionados")

        return {'FINISHED'}


#EscalaMenos1
# --- Propiedad para guardar el texto del botón ---
def get_button_label(self):
    return self.get("_scale_z_label", "Restar 0.1 en Z")

def set_button_label(self, value):
    self["_scale_z_label"] = value

# --- Operador: Restar 0.1 en Z ---
class OBJECT_OT_scale_z_minus(bpy.types.Operator):
    bl_idname = "object.scale_z_minus"
    bl_label = "Restar 0.1 en Z"
    bl_description = "Resta 0.1 en la escala Z de los objetos seleccionados"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                obj.scale.z -= 0.1

        # Cambiar texto del botón
        context.scene.scale_z_label = "Escalado"
        return {'FINISHED'}


bpy.types.Scene.scale_z_label = bpy.props.StringProperty(
    name="Botón Z",
    get=get_button_label,
    set=set_button_label
)

# --- Operador: Igualar Z a X ---
class OBJECT_OT_scale_z_equal_x(bpy.types.Operator):
    bl_idname = "object.scale_z_equal_x"
    bl_label = "Escala Original"
    bl_description = "Iguala la escala Z al valor de la escala X en los objetos seleccionados"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                obj.scale.z = obj.scale.x

        # Regresar el botón al texto original
        context.scene.scale_z_label = "Restar 0.1 en Z"
        return {'FINISHED'}


#Mover En Z 1
# Operador para subir en Z local
class OBJECT_OT_move_z_up(bpy.types.Operator):
    bl_idname = "object.move_z_up"
    bl_label = "Subir +1 mm"
    bl_description = "Mueve el objeto 1 mm en su eje Z local, sin importar la escala"

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                # Vector Z local
                local_offset = mathutils.Vector((0, 0, 0.1))  # 1 mm = 0.001 m
                # Ajustar por la escala del objeto
                world_offset = (obj.matrix_world.to_3x3() @ local_offset) / obj.scale.z
                obj.location += world_offset
        context.scene.z_up_count += 1
        return {'FINISHED'}
    
    # Operador para bajar en Z local
class OBJECT_OT_move_z_down(bpy.types.Operator):
    bl_idname = "object.move_z_down"
    bl_label = "Bajar -1 mm"
    bl_description = "Mueve el objeto -1 mm en su eje Z local, sin importar la escala"

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                local_offset = mathutils.Vector((0, 0, -0.1))  # -1 mm
                world_offset = (obj.matrix_world.to_3x3() @ local_offset) / obj.scale.z
                obj.location += world_offset
        context.scene.z_down_count += 1
        return {'FINISHED'}
    

#Seleccionar Rounds, Prongs, Cutter

# --------- Operadores de Seleccion ----------
class OBJECT_OT_select_round(bpy.types.Operator):
    bl_idname = "object.select_round"
    bl_label = "Round"
    bl_description = "Selecciona todos los objetos que empiecen con 'Round'"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in context.scene.objects:
            if obj.name.startswith("Round"):
                obj.select_set(True)
        return {"FINISHED"}


class OBJECT_OT_select_prongs(bpy.types.Operator):
    bl_idname = "object.select_prongs"
    bl_label = "Prongs"
    bl_description = "Selecciona todos los objetos que empiecen con 'Prongs'"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in context.scene.objects:
            if obj.name.startswith("Prongs"):
                obj.select_set(True)
        return {"FINISHED"}


class OBJECT_OT_select_cutter(bpy.types.Operator):
    bl_idname = "object.select_cutter"
    bl_label = "Cutter"
    bl_description = "Selecciona todos los objetos que empiecen con 'Cutter'"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in context.scene.objects:
            if obj.name.startswith("Cutter"):
                obj.select_set(True)
        return {"FINISHED"}

#AplicarRotation y partsloose

class OBJECT_OT_apply_rotation(bpy.types.Operator):
    bl_idname = "object.apply_rotation_only"
    bl_label = "Apply Rotation"
    bl_description = "Aplica solo la rotación de los objetos seleccionados"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == "MESH":
                # Si comparte mesh, hacer copia (single user)
                if obj.data.users > 1:
                    obj.data = obj.data.copy()

                # Obtener solo la parte de rotación de la matriz mundial
                rot_matrix = obj.matrix_world.to_3x3().to_4x4()

                # Aplicar la rotación a la geometría
                obj.data.transform(rot_matrix)

                # Mantener ubicación y escala
                loc = obj.matrix_world.to_translation()
                scale = obj.matrix_world.to_scale()

                obj.matrix_world = (
                    mathutils.Matrix.Translation(loc) @
                    mathutils.Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))
                )

        return {'FINISHED'}


class OBJECT_OT_separate_loose_parts(bpy.types.Operator):
    bl_idname = "object.separate_loose_parts"
    bl_label = "Separate Loose"
    bl_description = "Divide la geometría seleccionada en partes separadas (By Loose Parts)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Guardar objetos seleccionados
        selected_objs = context.selected_objects

        bpy.ops.object.mode_set(mode='OBJECT')

        for obj in selected_objs:
            if obj.type == "MESH":
                # Activar objeto
                context.view_layer.objects.active = obj
                obj.select_set(True)

                # Entrar en modo edición y separar por Loose Parts
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.separate(type='LOOSE')
                bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}

# ------------------------------
# Panel en N
# ------------------------------

class VIEW3D_PT_snapz_panel(bpy.types.Panel):
    bl_label = "Jewelry Tools"
    bl_idname = "VIEW3D_PT_snapz_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Jewelry Tools'

    def draw(self, context):
        layout = self.layout
        props = context.scene.snapz_props
        scene = context.scene
        wm = context.window_manager
        scn = context.scene

        col = layout.column(align=True)
        col.prop(props, "target")
        col.prop(props, "direction", text="Dirección")
        col.prop(props, "align_rotation")
        col.prop(props, "offset")
        col.separator()
        col.prop(props, "backtrack")
        col.prop(props, "max_step")
        col.operator("object.snap_in_z", icon='SNAP_NORMAL')

        col.operator("object.apply_and_clear_constraints", icon='CONSTRAINT')
        col.separator()
        
        row = layout.row(align=True)
        row.operator("mesh.separar_loop_shrinkwrap_only", icon="MOD_SHRINKWRAP")
        row.operator("object.convert_to_curve", icon="CURVE_DATA")
        col.operator("object.jewelcraft_curve_distribute", text="Distribuir en Curva")
    
        row = layout.row(align=True)
        row.operator("object.scale_z_minus", text=context.scene.scale_z_label, icon="TRIA_DOWN")
        row.operator("object.scale_z_equal_x", icon="FILE_REFRESH")
        
        row = layout.row(align=True)
        row.operator("object.move_z_up", text=f"▲ Subir +1 ({scene.z_up_count})")
        row.operator("object.move_z_down", text=f"▼ Bajar -1 ({scene.z_down_count})")
        

        layout.separator()
        layout.label(text="JewelCraft")
        row = layout.row(align=True)
        row.operator("object.select_round", icon="KEYTYPE_EXTREME_VEC")
        row.operator("object.select_prongs", icon="MESH_CAPSULE")
        row.operator("object.select_cutter", icon="MESH_CYLINDER")
        col.separator() 
        
        col = layout.column(align=True)
        col.operator("object.jewelcraft_gem_add", text="Añadir Gema")

        row = layout.row(align=True)
        row.operator("object.jewelcraft_prongs_add", text="Añadir Prongs")
        row.operator("object.jewelcraft_cutter_add", text="Añadir Cutter")

        row = layout.row(align=True)
        row.operator("object.apply_rotation_only", icon="FILE_REFRESH")
        row.operator("object.separate_loose_parts", icon="MESH_CUBE")

        col = layout.column(align=True)

        col.operator("object.jewelcraft_weight_display", text="Calcular Peso")

        col = layout.column(align=True)
        col.prop(wm.jewelcraft, "show_spacing", text="Mostrar Espaciado")
        col.prop(scn.jewelcraft, "overlay_show_all", text="Mostrar Todo")
        col.prop(scn.jewelcraft, "overlay_show_in_front", text="Mostrar Al Frente")
        



# ------------------------------
# Registro
# ------------------------------


classes = (
    #MoverenZ
    OBJECT_OT_move_z_up,
    OBJECT_OT_move_z_down,
    #MoverenZ
    SNAPZ_Props,
    OBJECT_OT_snap_in_z,
    OBJECT_OT_apply_and_clear_constraints,
    VIEW3D_PT_snapz_panel,
    #menos1
    OBJECT_OT_scale_z_minus, OBJECT_OT_scale_z_equal_x,
    #SeleccionarRoundsProngsCutter
    OBJECT_OT_select_round,
    OBJECT_OT_select_prongs,
    OBJECT_OT_select_cutter,
    OBJECT_OT_apply_rotation,
    OBJECT_OT_separate_loose_parts,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snapz_props = PointerProperty(type=SNAPZ_Props)
    #looptools
    bpy.utils.register_class(MESH_OT_separar_loop_shrinkwrap)
    bpy.utils.register_class(OBJECT_OT_convert_to_curve)
    #menos1
    bpy.types.Scene.scale_z_label = bpy.props.StringProperty(default="Restar 0.1 en Z")
    register_props()
    

def unregister():
    del bpy.types.Scene.snapz_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    #looptools
    bpy.utils.unregister_class(MESH_OT_separar_loop_shrinkwrap)
    bpy.utils.unregister_class(OBJECT_OT_convert_to_curve)
    #menos1
    del bpy.types.Scene.scale_z_label
    unregister_props()
if __name__ == "__main__":
    register()
