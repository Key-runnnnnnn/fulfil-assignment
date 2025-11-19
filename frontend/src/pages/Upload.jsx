import { useState, useRef, useEffect } from "react";
import {
  Upload as UploadIcon,
  FileText,
  CheckCircle,
  AlertCircle,
  Clock,
  TrendingUp,
} from "lucide-react";
import { uploadAPI } from "../services/api";
import {
  Card,
  Button,
  ProgressBar,
  Alert,
  Spinner,
  Badge,
} from "../components/UI";

const Upload = () => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);
  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    loadRecentJobs();
  }, []);

  useEffect(() => {
    if (jobId && jobStatus?.status === "processing") {
      const eventSource = uploadAPI.streamProgress(jobId);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setJobStatus(data);

        if (data.status === "completed" || data.status === "failed") {
          eventSource.close();
          loadRecentJobs();
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        pollJobStatus();
      };

      return () => {
        eventSource.close();
      };
    }
  }, [jobId, jobStatus?.status]);

  const loadRecentJobs = async () => {
    try {
      const response = await uploadAPI.getAllJobs();
      setRecentJobs(response.data.slice(0, 5));
    } catch (err) {
      console.error("Failed to load jobs:", err);
    }
  };

  const pollJobStatus = () => {
    const interval = setInterval(async () => {
      try {
        const response = await uploadAPI.getJobStatus(jobId);
        setJobStatus(response.data);

        if (
          response.data.status === "completed" ||
          response.data.status === "failed"
        ) {
          clearInterval(interval);
          loadRecentJobs();
        }
      } catch (err) {
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith(".csv")) {
        setError("Please select a CSV file");
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first");
      return;
    }

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const response = await uploadAPI.uploadCSV(file, (progressEvent) => {
        const progress = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        setUploadProgress(progress);
      });

      setJobId(response.data.job_id);
      setJobStatus({ status: "processing", progress: 0 });
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.endsWith(".csv")) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError("Please drop a CSV file");
    }
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat().format(num);
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending: { variant: "warning", icon: Clock },
      processing: { variant: "info", icon: TrendingUp },
      completed: { variant: "success", icon: CheckCircle },
      failed: { variant: "danger", icon: AlertCircle },
    };

    const config = statusConfig[status] || statusConfig.pending;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="w-3 h-3" />
        {status}
      </Badge>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Import Products</h1>
          <p className="mt-2 text-gray-600">
            Upload CSV files to import products into the database
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

        {/* Upload Section */}
        <Card className="p-8 mb-8">
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
              file
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <div className="flex flex-col items-center">
              {file ? (
                <>
                  <FileText className="w-16 h-16 text-blue-600 mb-4" />
                  <p className="text-lg font-medium text-gray-900 mb-1">
                    {file.name}
                  </p>
                  <p className="text-sm text-gray-500 mb-4">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </>
              ) : (
                <>
                  <UploadIcon className="w-16 h-16 text-gray-400 mb-4" />
                  <p className="text-lg font-medium text-gray-900 mb-1">
                    Drop your CSV file here
                  </p>
                  <p className="text-sm text-gray-500 mb-4">
                    or click to browse
                  </p>
                </>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
                id="file-upload"
              />

              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => document.getElementById("file-upload").click()}
                  disabled={uploading}
                >
                  Choose File
                </Button>
                {file && (
                  <Button
                    onClick={handleUpload}
                    disabled={uploading}
                    className="flex items-center gap-2"
                  >
                    {uploading ? (
                      <>
                        <Spinner size="sm" />
                        Uploading...
                      </>
                    ) : (
                      "Start Import"
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>

          {uploading && (
            <div className="mt-6">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Uploading file...</span>
                <span>{uploadProgress}%</span>
              </div>
              <ProgressBar progress={uploadProgress} />
            </div>
          )}
        </Card>

        {/* Current Job Progress */}
        {jobStatus &&
          jobStatus.status !== "completed" &&
          jobStatus.status !== "failed" && (
            <Card className="p-6 mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Processing Import
                </h2>
                {getStatusBadge(jobStatus.status)}
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Progress</span>
                    <span>{jobStatus.progress || 0}%</span>
                  </div>
                  <ProgressBar progress={jobStatus.progress || 0} />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm text-gray-500">Total Rows</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatNumber(jobStatus.total_rows || 0)}
                    </p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4">
                    <p className="text-sm text-green-600">Processed</p>
                    <p className="text-2xl font-bold text-green-700">
                      {formatNumber(jobStatus.processed_rows || 0)}
                    </p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-4">
                    <p className="text-sm text-red-600">Failed</p>
                    <p className="text-2xl font-bold text-red-700">
                      {formatNumber(jobStatus.failed_rows || 0)}
                    </p>
                  </div>
                </div>

                {jobStatus.error && (
                  <Alert type="error" message={jobStatus.error} />
                )}
              </div>
            </Card>
          )}

        {/* Recent Jobs */}
        {recentJobs.length > 0 && (
          <Card className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Recent Imports
            </h2>
            <div className="space-y-3">
              {recentJobs.map((job) => (
                <div
                  key={job.job_id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <p className="font-medium text-gray-900">
                        {job.filename}
                      </p>
                      {getStatusBadge(job.status)}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span>
                        {formatNumber(job.processed_rows || 0)} /{" "}
                        {formatNumber(job.total_rows || 0)} rows
                      </span>
                      {job.created_at && (
                        <span>{new Date(job.created_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                  {job.status === "processing" && (
                    <div className="w-24">
                      <ProgressBar progress={job.progress || 0} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Info Section */}
        <Card className="p-6 mt-6 bg-blue-50 border-blue-200">
          <h3 className="font-semibold text-blue-900 mb-2">
            CSV Format Requirements
          </h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>
              • Required columns:{" "}
              <code className="bg-blue-100 px-1 rounded">name</code>,{" "}
              <code className="bg-blue-100 px-1 rounded">sku</code>,{" "}
              <code className="bg-blue-100 px-1 rounded">description</code>
            </li>
            <li>
              • Optional columns:{" "}
              <code className="bg-blue-100 px-1 rounded">price</code>
            </li>
            <li>• SKU must be unique (case-insensitive)</li>
            <li>• Maximum file size: 100 MB</li>
            <li>• Processing is done in chunks for optimal performance</li>
          </ul>
        </Card>
      </div>
    </div>
  );
};

export default Upload;
