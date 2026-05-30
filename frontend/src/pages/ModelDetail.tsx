import { useState, useEffect, useCallback } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { ArrowLeft, ExternalLink, Package, Star, Download, Tag, FileBox, Globe, Images, Box, ImagePlus, Pencil, Plus } from "lucide-react";
import { api, ModelDetail as ModelDetailType } from "../api/client";
import FindOnWeb from "../components/FindOnWeb";
import STLViewer from "../components/STLViewer";
import ImagePicker from "../components/ImagePicker";
import MetadataEditor from "../components/MetadataEditor";
import { useNSFW } from "../context/NSFWContext";

type ViewMode = "images" | "3d";

export default function ModelDetail() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const backTo = (location.state as any)?.from ?? "/";
  const { showNSFW } = useNSFW();
  const [model, setModel] = useState<ModelDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeImage, setActiveImage] = useState<string | null>(null);
  const [showFindOnWeb, setShowFindOnWeb] = useState(false);
  const [showImagePicker, setShowImagePicker] = useState(false);
  const [editing, setEditing] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("images");
  const [nsfw, setNsfw] = useState(false);
  const [tags, setTags] = useState<string[]>([]);

  // sync local state from loaded model
  useEffect(() => {
    if (model) {
      setNsfw(model.nsfw);
      setTags(model.tags ?? []);
    }
  }, [model]);

  const addTag = async (tag: string) => {
    if (tags.includes(tag)) return;
    const next = [...tags, tag];
    setTags(next);
    await api.models.update(Number(id), { tags: next });
  };

  const toggleNSFW = async () => {
    const next = !nsfw;
    setNsfw(next);
    await api.models.setNSFW(Number(id), next);
  };

  const load = useCallback(() => {
    if (!id) return;
    api.models.get(Number(id)).then((m) => {
      setModel(m);
      const thumb = m.thumbnail_path
        ? api.fileUrl(m.thumbnail_path)
        : m.thumbnail_url ?? null;
      setActiveImage(thumb);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-8 text-gray-500 animate-pulse">Loading…</div>;
  if (!model) return <div className="p-8 text-gray-500">Model not found.</div>;

  const allImages = [
    model.thumbnail_path ? api.fileUrl(model.thumbnail_path) : model.thumbnail_url,
    ...model.image_paths.map(api.fileUrl),
  ].filter(Boolean) as string[];

  const hasSTLs = model.stl_files.some((f) =>
    f.filename.toLowerCase().endsWith(".stl")
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <Link to={backTo} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 mb-6 w-fit">
        <ArrowLeft size={14} /> Back to Library
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Left column — Images / 3D viewer */}
        <div className="flex flex-col gap-3">

          {/* View mode toggle */}
          {hasSTLs && (
            <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1 self-start">
              <button
                onClick={() => setViewMode("images")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                  viewMode === "images"
                    ? "bg-gray-700 text-gray-100"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                <Images size={14} /> Images
              </button>
              <button
                onClick={() => setViewMode("3d")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                  viewMode === "3d"
                    ? "bg-indigo-600 text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                <Box size={14} /> 3D View
              </button>
            </div>
          )}

          {/* Image view */}
          {viewMode === "images" && (
            <>
              <div className="aspect-square bg-gray-900 rounded-xl overflow-hidden border border-gray-800 relative group">
                {activeImage ? (
                  <img
                    src={activeImage}
                    alt={model.title ?? model.name}
                    className={`w-full h-full object-contain transition-all ${
                      nsfw && !showNSFW ? "blur-2xl" : ""
                    }`}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-700">
                    <Package size={64} />
                  </div>
                )}

                {/* NSFW detail overlay */}
                {nsfw && !showNSFW && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                    <span className="bg-black/70 text-red-400 text-sm font-bold px-3 py-1.5 rounded border border-red-800 tracking-widest">
                      NSFW
                    </span>
                    <p className="text-xs text-gray-500">Enable NSFW in the navbar to view</p>
                  </div>
                )}

                <button
                  onClick={() => setShowImagePicker(true)}
                  className="absolute bottom-3 right-3 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-black/60 hover:bg-black/80 text-gray-300 hover:text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <ImagePlus size={13} /> Change image
                </button>
              </div>
              {allImages.length > 1 && (
                <div className="flex gap-2 flex-wrap">
                  {allImages.map((img, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveImage(img)}
                      className={`w-16 h-16 rounded-lg overflow-hidden border-2 transition-colors ${
                        activeImage === img
                          ? "border-indigo-500"
                          : "border-gray-800 hover:border-gray-600"
                      }`}
                    >
                      <img src={img} alt="" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {/* 3D view */}
          {viewMode === "3d" && (
            <STLViewer
              files={model.stl_files}
              getUrl={api.stlUrl}
            />
          )}
        </div>

        {/* Right column — Info */}
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              {model.character && (
                <p className="text-sm text-indigo-400 mb-1">{model.character}</p>
              )}
              <h1 className="text-2xl font-bold text-gray-100">{model.title || model.name}</h1>
              {model.creator && (
                <p className="text-gray-400 mt-1">by {model.creator.name}</p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={toggleNSFW}
                title={nsfw ? "Mark as SFW" : "Mark as NSFW"}
                className={`px-3 py-1.5 rounded border text-sm transition-colors ${
                  nsfw
                    ? "bg-red-950/60 border-red-800 text-red-400 hover:bg-red-900/60"
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200"
                }`}
              >
                {nsfw ? "NSFW ✓" : "NSFW"}
              </button>
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-indigo-500 text-sm text-gray-300 transition-colors"
              >
                <Pencil size={14} />
                Edit
              </button>
              <button
                onClick={() => setShowFindOnWeb(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-indigo-500 text-sm text-gray-300 transition-colors"
              >
                <Globe size={14} />
                Find on Web
              </button>
            </div>
          </div>

          {/* ---- Edit mode ---- */}
          {editing && (
            <MetadataEditor
              model={model}
              onSaved={() => { setEditing(false); load(); }}
              onCancel={() => setEditing(false)}
            />
          )}

          {/* ---- Display mode ---- */}
          {!editing && (<>

          {/* Stats row */}
          <div className="flex items-center gap-4 text-sm text-gray-400">
            {model.rating != null && (
              <span className="flex items-center gap-1 text-yellow-400">
                <Star size={14} fill="currentColor" />
                {model.rating.toLocaleString()}
              </span>
            )}
            {model.download_count != null && (
              <span className="flex items-center gap-1">
                <Download size={14} />
                {model.download_count.toLocaleString()}
              </span>
            )}
            {model.source_site && (
              <span className="capitalize bg-gray-800 px-2 py-0.5 rounded text-xs">
                {model.source_site}
              </span>
            )}
            {model.license && (
              <span className="bg-gray-800 px-2 py-0.5 rounded text-xs">{model.license}</span>
            )}
          </div>

          {model.source_url && (
            <a
              href={model.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 w-fit"
            >
              <ExternalLink size={14} />
              View on {model.source_site ?? "source"}
            </a>
          )}

          {model.description && (
            <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-line line-clamp-6">
              {model.description}
            </p>
          )}

          {/* User tags */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <span key={tag} className="flex items-center gap-1 text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded-full">
                  <Tag size={10} />
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Auto-detected tags — click to promote to user tags */}
          {(model.auto_tags ?? []).length > 0 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs text-gray-600">Auto-detected · click to add as tag</p>
              <div className="flex flex-wrap gap-1.5">
                {model.auto_tags.map((tag) => {
                  const already = tags.includes(tag);
                  return (
                    <button
                      key={tag}
                      onClick={() => addTag(tag)}
                      disabled={already}
                      title={already ? "Already a tag" : "Add as tag"}
                      className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors ${
                        already
                          ? "bg-indigo-900/30 border-indigo-800 text-indigo-400 cursor-default"
                          : "bg-gray-800/60 border-gray-700 text-gray-500 hover:border-indigo-500 hover:text-indigo-400 hover:bg-indigo-950/30"
                      }`}
                    >
                      {already ? <Tag size={9} /> : <Plus size={9} />}
                      {tag}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* STL Files list */}
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <FileBox size={14} />
              Files ({model.stl_files.length})
            </h3>
            <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
              {model.stl_files.map((f) => (
                <a
                  key={f.id}
                  href={api.stlUrl(f.path)}
                  download={f.filename}
                  className="flex items-center justify-between text-xs bg-gray-900 border border-gray-800 hover:border-gray-600 px-3 py-2 rounded transition-colors"
                >
                  <span className="text-gray-300 truncate mr-2">{f.filename}</span>
                  {f.size_bytes && (
                    <span className="text-gray-600 shrink-0">
                      {(f.size_bytes / 1024 / 1024).toFixed(1)} MB
                    </span>
                  )}
                </a>
              ))}
            </div>
          </div>

          <p className="text-xs text-gray-700 break-all mt-auto">{model.folder_path}</p>

          </>)} {/* end display mode */}
        </div>
      </div>

      {showImagePicker && (
        <ImagePicker
          modelId={model.id}
          currentPath={model.thumbnail_path}
          onApplied={() => { setShowImagePicker(false); load(); }}
          onClose={() => setShowImagePicker(false)}
        />
      )}

      {showFindOnWeb && (
        <FindOnWeb
          modelId={model.id}
          modelName={model.title || model.name}
          onApplied={() => { setShowFindOnWeb(false); load(); }}
          onClose={() => setShowFindOnWeb(false)}
        />
      )}
    </div>
  );
}
