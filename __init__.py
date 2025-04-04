bl_info = {
    "name": "SRT Subtitle Importer/Exporter",
    "author": "poyakong",
    "version": (0, 0, 1),
    "blender": (2, 83, 0),
    "location": "Sequencer > SRT",
    "description": "Import/Export SRT subtitle files to/from VSE strips",
    "category": "Sequencer",
}

# import bpy for Blender Python API
import bpy
# import re from the Python standard library, for regular expressions
import re
# import os for file path handling
import os
# import props for custom properties
from bpy.props import StringProperty, IntProperty, FloatProperty ,BoolProperty
# import operators for custom operators
from bpy.types import Operator, Menu
# import io_utils for custom import/export operators
from bpy_extras.io_utils import ImportHelper, ExportHelper

# SRT time format: 00:00:00,000
def parse_srt_time(time_str):
    # Convert SRT time format to seconds
    hours, minutes, seconds = time_str.replace(',', '.').split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

def format_srt_time(seconds):
    # Convert seconds to SRT time format
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

# Get scene FPS
def get_scene_fps(scene):
    fps = scene.render.fps / scene.render.fps_base
    return fps

# Operators
class SEQUENCER_OT_ImportSRT(Operator, ImportHelper):
    bl_idname = "sequencer.import_srt"
    bl_label = "Import SRT"
    bl_description = "Import subtitles from SRT file"
    
    filename_ext = ".srt"
    filter_glob: StringProperty(default="*.srt", options={'HIDDEN'})
    
    start_frame: IntProperty(
        name="Start Frame",
        description="Frame to start placing subtitles",
        default=1
    )

    subtitle_channel: IntProperty(
        name="Subtitle Channel",
        description="Channel to place subtitles",
        default=1,
        min=1,
        max=32
    )
    
    use_scene_fps: BoolProperty(
        name="Use Scene FPS",
        description="Use the scene's FPS setting instead of a custom value",
        default=True
    )
    
    custom_fps: FloatProperty(
        name="Custom FPS",
        description="Custom frames per second for conversion (only used if 'Use Scene FPS' is off)",
        default=24.0,
        min=1.0
    )
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "start_frame")
        layout.prop(self, "subtitle_channel")
        layout.prop(self, "use_scene_fps")
        
        # Only show custom FPS option if use_scene_fps is off
        if not self.use_scene_fps:
            layout.prop(self, "custom_fps")
        else:
            # Display the current scene FPS (read-only)
            fps = get_scene_fps(context.scene)
            layout.label(text=f"Current Scene FPS: {fps:.3f}")
    
    def execute(self, context):
        try:
            # Determine which FPS to use
            if self.use_scene_fps:
                fps = get_scene_fps(context.scene)
            else:
                fps = self.custom_fps
            
            # Open and read the SRT file
            with open(self.filepath, 'r', encoding='utf-8-sig') as file:
                content = file.read()
            
            # Regular expression to parse SRT file
            # Matches each subtitle entry, with the following groups:
            # 1: index (Multiple digits)
            # 2: start time (HH:MM:SS,MMM)
            # 3: end time (HH:MM:SS,MMM)
            # 4: text (Texts until [a digits with a newline] or [EOF])
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n\d+\n|$)'
            matches = re.findall(pattern, content)
            
            if not matches:
                self.report({'ERROR'}, "No subtitles found in the SRT file")
                return {'CANCELLED'}
            
            # Get the current sequence editor
            scene = context.scene
            if not scene.sequence_editor:
                scene.sequence_editor_create()
            
            seq_editor = scene.sequence_editor
            
            # Add each subtitle as a text strip
            for index, start_time, end_time, text in matches:
                # Convert times to seconds
                start_sec = parse_srt_time(start_time)
                end_sec = parse_srt_time(end_time)
                
                # Convert seconds to frames
                start_frame = int(self.start_frame + start_sec * fps)
                end_frame = int(self.start_frame + end_sec * fps)
                duration = end_frame - start_frame
                
                # Clean up text (remove extra newlines at end)
                text = text.strip()
                
                # Create text strip
                text_strip = seq_editor.sequences.new_effect(
                    name=f"Subtitle {index}",
                    type='TEXT',
                    channel=self.subtitle_channel,
                    frame_start=start_frame,
                    frame_end=start_frame + duration
                )
                
                # Set text properties
                text_strip.text = text
                text_strip.font_size = 24
                
                # Position at bottom center
                text_strip.location[1] = 0.1  # Y location (vertical position)
                text_strip.use_shadow = True
                text_strip.shadow_color = (0, 0, 0, 1)  # Black shadow
                text_strip.blend_type = 'ALPHA_OVER'
                
                # TextSequence doesn't have align_x, but we can set alignment in Blender ≥ 2.8
                # with the 'text_align' property if it exists
                if hasattr(text_strip, 'text_align'):
                    text_strip.text_align = 'CENTER'
            
            # Get file name
            filename = os.path.basename(self.filepath)
            self.report({'INFO'}, f"Success. From [{filename}] there are [{len(matches)}] subtitles imported using FPS: [{fps:.3f}]")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error importing SRT: {str(e)}")
            return {'CANCELLED'}

class SEQUENCER_OT_ExportSRT(Operator, ExportHelper):
    bl_idname = "sequencer.export_srt"
    bl_label = "Export SRT"
    bl_description = "Export selected text strips as SRT file"
    
    filename_ext = ".srt"
    filter_glob: StringProperty(default="*.srt", options={'HIDDEN'})
    
    use_scene_fps: BoolProperty(
        name="Use Scene FPS",
        description="Use the scene's FPS setting instead of a custom value",
        default=True
    )
    
    custom_fps: FloatProperty(
        name="Custom FPS",
        description="Custom frames per second for conversion (only used if 'Use Scene FPS' is off)",
        default=24.0,
        min=1.0
    )
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "use_scene_fps")
        
        # Only show custom FPS option if use_scene_fps is off
        if not self.use_scene_fps:
            layout.prop(self, "custom_fps")
        else:
            # Display the current scene FPS (read-only)
            fps = get_scene_fps(context.scene)
            layout.label(text=f"Current Scene FPS: {fps:.3f}")
    
    def execute(self, context):
        scene = context.scene
        if not scene.sequence_editor:
            self.report({'ERROR'}, "No sequence editor found")
            return {'CANCELLED'}
        
        # Determine which FPS to use
        if self.use_scene_fps:
            fps = get_scene_fps(scene)
        else:
            fps = self.custom_fps
        
        # Get selected text strips
        selected_strips = [strip for strip in context.selected_sequences if strip.type == 'TEXT']
        
        if not selected_strips:
            self.report({'ERROR'}, "No text strips selected")
            return {'CANCELLED'}
        
        # Sort strips by start frame
        selected_strips.sort(key=lambda strip: strip.frame_start)
        
        # Write SRT file
        try:
            with open(self.filepath, 'w', encoding='utf-8') as file:
                for i, strip in enumerate(selected_strips, 1):
                    # Calculate start and end times in SRT format
                    start_sec = (strip.frame_start - 1) / fps
                    end_sec = strip.frame_final_end / fps
                    
                    start_time = format_srt_time(start_sec)
                    end_time = format_srt_time(end_sec)
                    
                    # Write subtitle entry
                    file.write(f"{i}\n")
                    file.write(f"{start_time} --> {end_time}\n")
                    file.write(f"{strip.text}\n\n")
            
            # Get file name
            filename = os.path.basename(self.filepath)
            self.report({'INFO'}, f"Success. From [{filename}] there are [{len(selected_strips)}] subtitles exported using FPS: [{fps:.3f}]")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error exporting SRT: {str(e)}")
            return {'CANCELLED'}

# Menu class
class SEQUENCER_MT_srt_menu(Menu):
    bl_label = "SRT"
    bl_idname = "SEQUENCER_MT_srt_menu"
    
    def draw(self, context):
        layout = self.layout
        layout.operator(SEQUENCER_OT_ImportSRT.bl_idname, text="Import SRT")
        layout.operator(SEQUENCER_OT_ExportSRT.bl_idname, text="Export SRT")

# Menu integration function
def draw_srt_menu(self, context):
    layout = self.layout
    layout.menu(SEQUENCER_MT_srt_menu.bl_idname)

def register():
    # Register classes
    bpy.utils.register_class(SEQUENCER_OT_ImportSRT)
    bpy.utils.register_class(SEQUENCER_OT_ExportSRT)
    bpy.utils.register_class(SEQUENCER_MT_srt_menu)
    
    # Add to VSE menu
    bpy.types.SEQUENCER_MT_editor_menus.append(draw_srt_menu)

def unregister():
    # Remove from VSE menu
    bpy.types.SEQUENCER_MT_editor_menus.remove(draw_srt_menu)
    
    # Unregister classes
    bpy.utils.unregister_class(SEQUENCER_MT_srt_menu)
    bpy.utils.unregister_class(SEQUENCER_OT_ExportSRT)
    bpy.utils.unregister_class(SEQUENCER_OT_ImportSRT)

if __name__ == "__main__":
    register()