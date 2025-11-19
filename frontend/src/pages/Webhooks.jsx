import { useState, useEffect } from "react";
import { Plus, Trash2, Edit2, Power, Zap, RefreshCw } from "lucide-react";
import { webhooksAPI } from "../services/api";
import {
  Card,
  Button,
  Input,
  Modal,
  Alert,
  Spinner,
  Badge,
} from "../components/UI";

const Webhooks = () => {
  const [webhooks, setWebhooks] = useState([]);
  const [eventTypes, setEventTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState("create");
  const [currentWebhook, setCurrentWebhook] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [testing, setTesting] = useState({});
  const [formData, setFormData] = useState({
    url: "",
    event_type: "import.completed",
    is_active: true,
    headers: {},
  });
  const [headerKey, setHeaderKey] = useState("");
  const [headerValue, setHeaderValue] = useState("");

  useEffect(() => {
    loadWebhooks();
    loadEventTypes();
  }, []);

  const loadWebhooks = async () => {
    setLoading(true);
    try {
      const response = await webhooksAPI.getAll();
      setWebhooks(response.data || []);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  };

  const loadEventTypes = async () => {
    try {
      const response = await webhooksAPI.getEventTypes();
      setEventTypes(response.data || []);
    } catch (err) {
      console.error("Failed to load event types:", err);
    }
  };

  const handleCreate = () => {
    setModalMode("create");
    setFormData({
      url: "",
      event_type: "import.completed",
      is_active: true,
      headers: {},
    });
    setShowModal(true);
  };

  const handleEdit = (webhook) => {
    setModalMode("edit");
    setCurrentWebhook(webhook);
    setFormData({
      url: webhook.url,
      event_type: webhook.event_type,
      is_active: webhook.is_active,
      headers: webhook.headers || {},
    });
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (!formData.url) {
      setError("URL is required");
      return;
    }

    try {
      if (modalMode === "create") {
        await webhooksAPI.create(formData);
        setSuccess("Webhook created successfully");
      } else {
        await webhooksAPI.update(currentWebhook.id, formData);
        setSuccess("Webhook updated successfully");
      }

      setShowModal(false);
      loadWebhooks();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Operation failed");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Are you sure you want to delete this webhook?")) return;

    try {
      await webhooksAPI.delete(id);
      setSuccess("Webhook deleted successfully");
      loadWebhooks();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete webhook");
    }
  };

  const handleToggle = async (id) => {
    try {
      await webhooksAPI.toggle(id);
      setSuccess("Webhook status updated");
      loadWebhooks();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to toggle webhook");
    }
  };

  const handleTest = async (id) => {
    setTesting({ ...testing, [id]: true });
    try {
      await webhooksAPI.test(id);
      setSuccess("Test webhook sent! Check your endpoint logs.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to test webhook");
    } finally {
      setTesting({ ...testing, [id]: false });
    }
  };

  const addHeader = () => {
    if (headerKey && headerValue) {
      setFormData({
        ...formData,
        headers: { ...formData.headers, [headerKey]: headerValue },
      });
      setHeaderKey("");
      setHeaderValue("");
    }
  };

  const removeHeader = (key) => {
    const newHeaders = { ...formData.headers };
    delete newHeaders[key];
    setFormData({ ...formData, headers: newHeaders });
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Webhooks</h1>
          <p className="mt-2 text-gray-600">
            Configure webhooks to receive notifications for events
          </p>
        </div>

        {error && (
          <Alert
            type="error"
            message={error}
            onClose={() => setError(null)}
            className="mb-6"
          />
        )}
        {success && (
          <Alert
            type="success"
            message={success}
            onClose={() => setSuccess(null)}
            className="mb-6"
          />
        )}

        {/* Actions */}
        <div className="flex justify-between items-center mb-6">
          <Button
            onClick={loadWebhooks}
            variant="outline"
            className="flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
          <Button onClick={handleCreate} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add Webhook
          </Button>
        </div>

        {/* Webhooks List */}
        {loading ? (
          <Card className="p-20">
            <div className="flex justify-center">
              <Spinner size="lg" />
            </div>
          </Card>
        ) : webhooks.length === 0 ? (
          <Card className="p-20">
            <div className="text-center">
              <p className="text-gray-500 text-lg mb-4">
                No webhooks configured
              </p>
              <Button onClick={handleCreate}>Add your first webhook</Button>
            </div>
          </Card>
        ) : (
          <div className="space-y-4">
            {webhooks.map((webhook) => (
              <Card
                key={webhook.id}
                className="p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {webhook.url}
                      </h3>
                      <Badge
                        variant={webhook.is_active ? "success" : "default"}
                      >
                        {webhook.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>

                    <div className="space-y-2 text-sm text-gray-600">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">Event:</span>
                        <code className="bg-gray-100 px-2 py-1 rounded">
                          {webhook.event_type}
                        </code>
                      </div>

                      {webhook.headers &&
                        Object.keys(webhook.headers).length > 0 && (
                          <div>
                            <span className="font-medium">Headers:</span>
                            <div className="mt-1 space-y-1">
                              {Object.entries(webhook.headers).map(
                                ([key, value]) => (
                                  <div
                                    key={key}
                                    className="bg-gray-50 px-2 py-1 rounded"
                                  >
                                    <span className="font-mono text-xs">
                                      {key}: {value}
                                    </span>
                                  </div>
                                )
                              )}
                            </div>
                          </div>
                        )}

                      {webhook.created_at && (
                        <div className="text-gray-500">
                          Created:{" "}
                          {new Date(webhook.created_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleTest(webhook.id)}
                      disabled={testing[webhook.id]}
                      className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors disabled:opacity-50"
                      title="Test webhook"
                    >
                      {testing[webhook.id] ? (
                        <Spinner size="sm" />
                      ) : (
                        <Zap className="w-5 h-5" />
                      )}
                    </button>
                    <button
                      onClick={() => handleToggle(webhook.id)}
                      className={`p-2 rounded-lg transition-colors ${
                        webhook.is_active
                          ? "text-green-600 hover:bg-green-50"
                          : "text-gray-400 hover:bg-gray-50"
                      }`}
                      title={webhook.is_active ? "Disable" : "Enable"}
                    >
                      <Power className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleEdit(webhook)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleDelete(webhook.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Event Types Info */}
        <Card className="p-6 mt-6 bg-blue-50 border-blue-200">
          <h3 className="font-semibold text-blue-900 mb-3">
            Available Event Types
          </h3>
          <div className="space-y-2">
            {eventTypes.map((event) => (
              <div key={event} className="flex items-center gap-2">
                <code className="bg-blue-100 px-2 py-1 rounded text-sm text-blue-800">
                  {event}
                </code>
                <span className="text-sm text-blue-700">
                  {event === "import.completed" &&
                    "- Triggered when CSV import completes successfully"}
                  {event === "import.failed" &&
                    "- Triggered when CSV import fails"}
                  {event === "product.created" &&
                    "- Triggered when a product is created"}
                  {event === "product.updated" &&
                    "- Triggered when a product is updated"}
                  {event === "product.deleted" &&
                    "- Triggered when a product is deleted"}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Create/Edit Modal */}
        <Modal
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          title={modalMode === "create" ? "Add New Webhook" : "Edit Webhook"}
          size="lg"
        >
          <div className="space-y-4">
            <Input
              label="Webhook URL *"
              type="url"
              value={formData.url}
              onChange={(e) =>
                setFormData({ ...formData, url: e.target.value })
              }
              placeholder="https://your-domain.com/webhook"
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Event Type *
              </label>
              <select
                value={formData.event_type}
                onChange={(e) =>
                  setFormData({ ...formData, event_type: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {eventTypes.map((event) => (
                  <option key={event} value={event}>
                    {event}
                  </option>
                ))}
              </select>
            </div>

            {/* Custom Headers */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Custom Headers
              </label>
              <div className="space-y-2">
                {Object.entries(formData.headers).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center gap-2 bg-gray-50 p-2 rounded"
                  >
                    <span className="flex-1 font-mono text-sm">
                      {key}: {value}
                    </span>
                    <button
                      onClick={() => removeHeader(key)}
                      className="text-red-600 hover:text-red-800"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}

                <div className="flex gap-2">
                  <Input
                    placeholder="Header key"
                    value={headerKey}
                    onChange={(e) => setHeaderKey(e.target.value)}
                    className="flex-1"
                  />
                  <Input
                    placeholder="Header value"
                    value={headerValue}
                    onChange={(e) => setHeaderValue(e.target.value)}
                    className="flex-1"
                  />
                  <Button onClick={addHeader} variant="outline" size="sm">
                    Add
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="webhook_active"
                checked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label
                htmlFor="webhook_active"
                className="text-sm font-medium text-gray-700"
              >
                Active
              </label>
            </div>

            <div className="flex gap-3 pt-4">
              <Button onClick={handleSubmit} className="flex-1">
                {modalMode === "create" ? "Create" : "Update"}
              </Button>
              <Button
                onClick={() => setShowModal(false)}
                variant="secondary"
                className="flex-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
};

export default Webhooks;
