const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Enhanced VS Code extension for formal verification
 * Includes progress tracking, better error handling, and diagnostics integration
 */

let outputChannel;
let statusBarItem;
let currentVerificationProcess = null;

function activate(context) {
    console.log('Formal Verifier extension is now active');
    
    // Initialize components
    outputChannel = vscode.window.createOutputChannel('Formal Verifier');
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = "$(check) Formal Verifier";
    statusBarItem.tooltip = "Click to run formal verification";
    statusBarItem.command = 'formalVerifier.run';
    statusBarItem.show();
    
    // Register commands
    let runCommand = vscode.commands.registerCommand('formalVerifier.run', runVerification);
    let stopCommand = vscode.commands.registerCommand('formalVerifier.stop', stopVerification);
    let configureCommand = vscode.commands.registerCommand('formalVerifier.configure', configureExtension);
    let showOutputCommand = vscode.commands.registerCommand('formalVerifier.showOutput', () => {
        outputChannel.show();
    });
    
    context.subscriptions.push(runCommand, stopCommand, configureCommand, showOutputCommand, outputChannel, statusBarItem);
    
    // Listen for configuration changes
    vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration('formalVerifier')) {
            outputChannel.appendLine('Configuration changed, reloading settings...');
        }
    });
}

async function runVerification() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage("No active file. Please open a C source file.");
        return;
    }
    
    const document = editor.document;
    const filePath = document.fileName;
    const fileExtension = path.extname(filePath);
    
    // Validate file type
    const supportedExtensions = getConfig().get('supportedExtensions', ['.c', '.h']);
    if (!supportedExtensions.includes(fileExtension)) {
        vscode.window.showErrorMessage(`Unsupported file type: ${fileExtension}. Supported types: ${supportedExtensions.join(', ')}`);
        return;
    }
    
    // Save file if needed
    if (document.isDirty && getConfig().get('autoSaveBeforeVerify', true)) {
        await document.save();
    }
    
    // Check if verification is already running
    if (currentVerificationProcess) {
        const choice = await vscode.window.showWarningMessage(
            'Verification is already running. Do you want to stop it and start a new one?',
            'Stop and Restart', 'Continue Current'
        );
        
        if (choice === 'Stop and Restart') {
            stopVerification();
        } else {
            return;
        }
    }
    
    // Start verification
    await startVerification(filePath);
}

async function startVerification(filePath) {
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(filePath));
    const projectRoot = workspaceFolder ? workspaceFolder.uri.fsPath : path.dirname(filePath);
    
    // Update UI
    statusBarItem.text = "$(sync~spin) Verifying...";
    statusBarItem.tooltip = "Formal verification in progress - click to stop";
    statusBarItem.command = 'formalVerifier.stop';
    
    outputChannel.clear();
    outputChannel.appendLine(`Starting formal verification of: ${filePath}`);
    outputChannel.appendLine(`Project root: ${projectRoot}`);
    outputChannel.appendLine('=====================================');
    outputChannel.show(true);
    
    // Clear previous diagnostics
    clearDiagnostics();
    
    // Prepare command
    const pythonPath = getConfig().get('pythonPath', 'python3');
    const scriptPath = getPythonScriptPath();
    const command = `"${pythonPath}" "${scriptPath}" "${filePath}"`;
    const options = {
        cwd: projectRoot,
        env: { ...process.env, PYTHONPATH: path.dirname(scriptPath) }
    };
    
    outputChannel.appendLine(`Running: ${command}`);
    outputChannel.appendLine('');
    
    // Show progress notification
    return vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Formal Verification",
        cancellable: true
    }, (progress, token) => {
        return new Promise((resolve, reject) => {
            // Handle cancellation
            token.onCancellationRequested(() => {
                if (currentVerificationProcess) {
                    currentVerificationProcess.kill();
                    outputChannel.appendLine('Verification cancelled by user');
                }
                resolve();
            });
            
            // Start the verification process
            progress.report({ increment: 0, message: "Starting verification pipeline..." });
            
            currentVerificationProcess = cp.exec(command, options, (error, stdout, stderr) => {
                currentVerificationProcess = null;
                
                // Reset UI
                statusBarItem.text = "$(check) Formal Verifier";
                statusBarItem.tooltip = "Click to run formal verification";
                statusBarItem.command = 'formalVerifier.run';
                
                if (error) {
                    outputChannel.appendLine(`Error: ${error.message}`);
                    if (stderr) {
                        outputChannel.appendLine(`Stderr: ${stderr}`);
                    }
                    vscode.window.showErrorMessage("Verification failed to run. Check output for details.");
                    reject(error);
                    return;
                }
                
                // Process results
                processVerificationResults(stdout, stderr, filePath);
                resolve();
            });
            
            // Handle stdout for progress updates
            currentVerificationProcess.stdout.on('data', (data) => {
                const output = data.toString();
                outputChannel.append(output);
                
                // Parse progress information
                const progressMatch = output.match(/Progress: (\d+)%/);
                if (progressMatch) {
                    const percentage = parseInt(progressMatch[1]);
                    progress.report({ increment: percentage - (progress._value || 0) });
                }
                
                // Parse stage information
                const stageMatch = output.match(/Stage: (.+)/);
                if (stageMatch) {
                    progress.report({ message: stageMatch[1] });
                }
            });
            
            // Handle stderr
            currentVerificationProcess.stderr.on('data', (data) => {
                outputChannel.append(data.toString());
            });
        });
    });
}

function stopVerification() {
    if (currentVerificationProcess) {
        currentVerificationProcess.kill();
        currentVerificationProcess = null;
        
        // Reset UI
        statusBarItem.text = "$(check) Formal Verifier";
        statusBarItem.tooltip = "Click to run formal verification";
        statusBarItem.command = 'formalVerifier.run';
        
        outputChannel.appendLine('Verification stopped by user');
        vscode.window.showInformationMessage('Verification stopped');
    }
}

function processVerificationResults(stdout, stderr, filePath) {
    try {
        // Try to parse JSON output
        let results;
        try {
            const jsonMatch = stdout.match(/VERIFICATION_RESULTS_START\n(.*?)\nVERIFICATION_RESULTS_END/s);
            if (jsonMatch) {
                results = JSON.parse(jsonMatch[1]);
            }
        } catch (e) {
            // Fallback to plain text processing
            results = { verified: false, errors: [stdout] };
        }
        
        if (results && results.verified) {
            vscode.window.showInformationMessage('✅ Formal verification successful!');
            outputChannel.appendLine('\n✅ Verification completed successfully');
        } else {
            const errors = results ? results.errors : ['Verification failed - check output for details'];
            vscode.window.showWarningMessage(`❌ Verification failed with ${errors.length} error(s)`);
            
            // Create diagnostics for errors
            createDiagnostics(filePath, errors);
        }
        
        // Show detailed results in output
        if (results) {
            outputChannel.appendLine('\n=== Verification Results ===');
            outputChannel.appendLine(JSON.stringify(results, null, 2));
        }
        
    } catch (error) {
        outputChannel.appendLine(`Error processing results: ${error.message}`);
        vscode.window.showErrorMessage('Error processing verification results');
    }
}

function createDiagnostics(filePath, errors) {
    const diagnostics = [];
    const diagnosticCollection = vscode.languages.createDiagnosticCollection('formalVerifier');
    
    errors.forEach(error => {
        // Try to parse line numbers from error messages
        const lineMatch = error.match(/line (\d+)/i);
        const line = lineMatch ? parseInt(lineMatch[1]) - 1 : 0; // VS Code uses 0-based indexing
        
        const diagnostic = new vscode.Diagnostic(
            new vscode.Range(line, 0, line, Number.MAX_SAFE_INTEGER),
            error,
            vscode.DiagnosticSeverity.Error
        );
        diagnostic.source = 'Formal Verifier';
        diagnostics.push(diagnostic);
    });
    
    diagnosticCollection.set(vscode.Uri.file(filePath), diagnostics);
}

function clearDiagnostics() {
    // Clear all diagnostics from our collection
    const diagnosticCollection = vscode.languages.createDiagnosticCollection('formalVerifier');
    diagnosticCollection.clear();
}

async function configureExtension() {
    const config = vscode.workspace.getConfiguration('formalVerifier');
    
    const items = [
        {
            label: 'Python Path',
            description: `Current: ${config.get('pythonPath', 'python3')}`,
            action: 'pythonPath'
        },
        {
            label: 'Auto Save Before Verify',
            description: `Current: ${config.get('autoSaveBeforeVerify', true)}`,
            action: 'autoSaveBeforeVerify'
        },
        {
            label: 'Supported Extensions',
            description: `Current: ${config.get('supportedExtensions', ['.c', '.h']).join(', ')}`,
            action: 'supportedExtensions'
        },
        {
            label: 'Open Settings',
            description: 'Open extension settings in VS Code',
            action: 'openSettings'
        }
    ];
    
    const selected = await vscode.window.showQuickPick(items, {
        placeHolder: 'Select configuration option'
    });
    
    if (!selected) return;
    
    switch (selected.action) {
        case 'pythonPath':
            const newPath = await vscode.window.showInputBox({
                prompt: 'Enter Python executable path',
                value: config.get('pythonPath', 'python3')
            });
            if (newPath) {
                await config.update('pythonPath', newPath, vscode.ConfigurationTarget.Workspace);
            }
            break;
            
        case 'autoSaveBeforeVerify':
            const autoSave = await vscode.window.showQuickPick(['true', 'false'], {
                placeHolder: 'Auto save before verification?'
            });
            if (autoSave) {
                await config.update('autoSaveBeforeVerify', autoSave === 'true', vscode.ConfigurationTarget.Workspace);
            }
            break;
            
        case 'openSettings':
            vscode.commands.executeCommand('workbench.action.openSettings', 'formalVerifier');
            break;
    }
}

function getPythonScriptPath() {
    // Get the path to the Python main script
    const extensionPath = vscode.extensions.getExtension('your-publisher.formal-verifier').extensionPath;
    return path.join(extensionPath, 'python', 'main.py');
}

function getConfig() {
    return vscode.workspace.getConfiguration('formalVerifier');
}

function deactivate() {
    if (currentVerificationProcess) {
        currentVerificationProcess.kill();
    }
}

module.exports = {
    activate,
    deactivate
};