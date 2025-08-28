const vscode = require('vscode');
const cp = require('child_process');

function activate(context) {
    let disposable = vscode.commands.registerCommand('formalVerifier.run', function () {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage("No active file.");
            return;
        }
        const filePath = editor.document.fileName;

        // Call Python backend
        cp.exec(`python3 ./python/main.py "${filePath}"`, (err, stdout, stderr) => {
            if (err) {
                vscode.window.showErrorMessage("Verification failed to run.");
                console.error(stderr);
                return;
            }
            vscode.window.showInformationMessage("Formal Verification Results Ready.");
            vscode.window.showInformationMessage(stdout); // crude, improve later
        });
    });

    context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
