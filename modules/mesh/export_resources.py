"""Own only temporary IDs explicitly allocated by the mesh exporter.

Cleanup runs on success and on exceptions. Disposable data is never selected
by name: a user may already own a collection named clonedMeshes or an orphan
mesh. Ported from the ZZtaii fork.
"""
from functools import wraps
import bpy

_scopes = []

class ExportResources:
	def __init__(self):
		self.view_layer = bpy.context.view_layer
		self.active = self.view_layer.objects.active
		self.selected = tuple(bpy.context.selected_objects)
		self.mode = self.active.mode if self.active is not None else None
		self.objects = []
		self.meshes = []
		self.armatures = []
		self.collection = None

	def cleanup(self):
		for obj in reversed(self.objects):
			try:
				bpy.data.objects.remove(obj, do_unlink=True)
			except ReferenceError:
				pass
		if self.collection is not None:
			try:
				bpy.data.collections.remove(self.collection)
			except ReferenceError:
				pass
		for values, registry in ((self.meshes, bpy.data.meshes),
								 (self.armatures, bpy.data.armatures)):
			for data in reversed(values):
				try:
					data.use_fake_user = False
					if data.users == 0:
						registry.remove(data)
				except ReferenceError:
					pass

	def restore_context(self):
		# The exporter temporarily activates and selects disposable clones.
		# Restore the user's selection, active object and mode even on failure.
		for obj in tuple(bpy.context.selected_objects):
			obj.select_set(False)
		for obj in self.selected:
			try:
				if self.view_layer.objects.get(obj.name) == obj:
					obj.select_set(True)
			except ReferenceError:
				pass
		try:
			active = self.active
			if active is not None and self.view_layer.objects.get(active.name) == active:
				self.view_layer.objects.active = active
				if self.mode and active.mode != self.mode:
					bpy.ops.object.mode_set(mode=self.mode)
			elif active is None:
				self.view_layer.objects.active = None
		except (ReferenceError, RuntimeError):
			pass


def _current_scope():
	return _scopes[-1] if _scopes else None


def track_object(obj):
	scope = _current_scope()
	if scope is not None:
		scope.objects.append(obj)
	return obj


def track_mesh(mesh):
	scope = _current_scope()
	if scope is not None:
		scope.meshes.append(mesh)
	return mesh


def track_armature(armature):
	scope = _current_scope()
	if scope is not None:
		scope.armatures.append(armature)
	return armature


def temporary_collection():
	scope = _scopes[-1]
	if scope.collection is None:
		scope.collection = bpy.data.collections.new("clonedMeshes")
		bpy.context.scene.collection.children.link(scope.collection)
	return scope.collection


def owned_export_resources(function):
	@wraps(function)
	def wrapped(*args, **kwargs):
		scope = ExportResources()
		_scopes.append(scope)
		try:
			return function(*args, **kwargs)
		finally:
			try:
				scope.cleanup()
			finally:
				try:
					scope.restore_context()
				finally:
					_scopes.pop()
	return wrapped
